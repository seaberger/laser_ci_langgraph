from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any, List, Tuple, Optional
import requests, pdfplumber, io
from bs4 import BeautifulSoup
from pathlib import Path
import tempfile
import hashlib
import os
from urllib.parse import urlparse
import re
from ..extraction import AdvancedHTMLExtractor, AdvancedPDFExtractor
from typing import Union


class Target(dict): ...


class BaseScraper(ABC):
    def __init__(self, targets: list[dict], force_refresh: bool = False):
        self._targets = targets
        self.force_refresh = force_refresh
        self.cache_dir = Path("data/pdf_cache")
        self.html_extractor = AdvancedHTMLExtractor()
        self.pdf_extractor = AdvancedPDFExtractor()

    @abstractmethod
    def vendor(self) -> str: ...

    def iter_targets(self) -> Iterable[Target]:
        for t in self._targets:
            pid = t["product_id"]
            if t.get("product_url"):
                yield {"product_id": pid, "url": t["product_url"], "kind": "html"}
            for ds in t.get("datasheets", []):
                yield {"product_id": pid, "url": ds, "kind": "pdf"}

    def fetch(self, url: str) -> tuple[int, str, str]:
        r = requests.get(url, timeout=30)
        ctype = (
            "pdf"
            if url.lower().endswith(".pdf")
            or "application/pdf" in r.headers.get("content-type", "")
            else "html"
        )
        text = ""
        if ctype == "html":
            text = r.text
        else:
            # Use pdfplumber as fallback for simple text extraction
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages)
        return r.status_code, ctype, text

    def extract_table_kv_pairs(self, html_text: str) -> dict:
        """Extract key-value pairs from HTML tables"""
        soup = BeautifulSoup(html_text, "html.parser")
        kv = {}
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    k = cells[0].get_text(" ", strip=True)
                    v = cells[1].get_text(" ", strip=True)
                    if k and v:
                        kv[k] = v
        return kv
    
    def extract_all_html_specs(self, html_text: str) -> dict:
        """Extract specs from HTML using advanced extraction methods"""
        return self.html_extractor.extract_all_specs(html_text)
    
    def extract_pdf_specs_with_docling(self, pdf_content: bytes) -> Tuple[str, dict]:
        """Extract text and structured data from PDF using advanced extraction"""
        try:
            return self.pdf_extractor.extract_specs(pdf_content)
        except Exception as e:
            print(f"Advanced extraction failed: {e}, falling back to pdfplumber")
            # Fallback to pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
                text = "\n".join(pages)
            return text, {}
    
    def calculate_content_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of content"""
        return hashlib.sha256(content).hexdigest()
    
    def get_pdf_cache_path(self, url: str) -> Path:
        """Generate cache path for PDF based on URL"""
        parsed = urlparse(url)
        vendor_dir = self.vendor().lower().replace(" ", "_").replace("(", "").replace(")", "")
        
        # Extract filename from URL
        filename = os.path.basename(parsed.path)
        if not filename.endswith('.pdf'):
            filename = hashlib.md5(url.encode()).hexdigest()[:8] + ".pdf"
        
        # Create path: data/pdf_cache/vendor/filename
        cache_path = self.cache_dir / vendor_dir / filename
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        return cache_path
    
    def should_skip_document(self, url: str, current_hash: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if document should be skipped based on content hash.
        Returns: (should_skip, cached_text, cached_file_path)
        """
        if self.force_refresh:
            return False, None, None
        
        # Check database for existing document with same URL and hash
        from ..db import SessionLocal
        from ..models import RawDocument
        
        s = SessionLocal()
        try:
            existing = s.query(RawDocument).filter_by(
                url=url,
                content_hash=current_hash
            ).order_by(RawDocument.fetched_at.desc()).first()
            
            if existing:
                # Content hasn't changed, skip processing
                return True, existing.text, existing.file_path
            
            return False, None, None
        finally:
            s.close()
    
    def cache_pdf(self, url: str, content: bytes) -> str:
        """Save PDF to cache and return the file path"""
        cache_path = self.get_pdf_cache_path(url)
        cache_path.write_bytes(content)
        return str(cache_path)
    
    def get_cached_pdf(self, url: str) -> Optional[bytes]:
        """Retrieve cached PDF if it exists"""
        if self.force_refresh:
            return None
            
        cache_path = self.get_pdf_cache_path(url)
        if cache_path.exists():
            return cache_path.read_bytes()
        return None
    
    def requires_browser(self, url: str, initial_response: Union[requests.Response, None] = None) -> bool:
        """
        Detect if a URL requires browser-based fetching.
        
        Indicators that browser is needed:
        1. PDF URL returns HTML instead of PDF content
        2. HTML has minimal content but lots of JavaScript
        3. Response contains SPA framework markers (React, Vue, Angular)
        4. Content-Type mismatch (PDF URL with HTML response)
        """
        # Fetch if not provided
        if initial_response is None:
            try:
                initial_response = requests.get(url, timeout=10, allow_redirects=True)
            except:
                return False
        
        content = initial_response.content
        content_type = initial_response.headers.get('content-type', '').lower()
        
        # Check 1: PDF URL returning HTML
        if url.lower().endswith('.pdf'):
            # If content starts with HTML doctype or tags, it's not a real PDF
            content_start = content[:500].lower()
            if b'<!doctype' in content_start or b'<html' in content_start:
                print(f"  → Detected: PDF URL returning HTML (requires browser)")
                return True
            # Check if it's actually a PDF
            if not content.startswith(b'%PDF'):
                print(f"  → Detected: PDF URL with non-PDF content (requires browser)")
                return True
        
        # For HTML pages, check for SPA indicators
        if 'text/html' in content_type:
            html_text = content.decode('utf-8', errors='ignore')
            
            # Check 2: Minimal content with heavy JavaScript
            # Count actual text content vs script tags
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, 'html.parser')
            
            # Remove script and style tags
            for tag in soup(['script', 'style', 'meta', 'link']):
                tag.decompose()
            
            text_content = soup.get_text(strip=True)
            
            # If very little text content compared to HTML size
            if len(text_content) < 500 and len(html_text) > 5000:
                print(f"  → Detected: Minimal content with heavy JavaScript (requires browser)")
                return True
            
            # Check 3: SPA framework markers
            spa_markers = [
                'data-react', 'react-root', '__react',  # React
                'ng-app', 'ng-controller', 'angular',   # Angular
                'v-app', 'vue-app', '__vue__',          # Vue
                'data-n-head', '__NUXT__',              # Nuxt/Vue
                '__NEXT_DATA__',                        # Next.js
                'ember-application',                     # Ember
                'svelte-'                                # Svelte
            ]
            
            html_lower = html_text.lower()
            for marker in spa_markers:
                if marker.lower() in html_lower:
                    print(f"  → Detected: SPA framework marker '{marker}' (requires browser)")
                    return True
            
            # Check for lazy-loaded content indicators
            if 'lazy-load' in html_lower or 'data-src' in html_lower:
                print(f"  → Detected: Lazy-loaded content (requires browser)")
                return True
        
        return False
    
    def fetch_with_browser(self, url: str) -> Tuple[int, str, str, str, Optional[str], Optional[dict]]:
        """
        Fetch content using Playwright browser for JavaScript-heavy sites.
        Returns: (status_code, content_type, text, content_hash, file_path, raw_specs)
        """
        try:
            from playwright.sync_api import sync_playwright
            import time
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                try:
                    print(f"  → Browser fetching: {url}")
                    response = page.goto(url, wait_until="networkidle", timeout=30000)
                    
                    if url.lower().endswith(".pdf"):
                        # Wait for potential redirect or download
                        time.sleep(2)
                        
                        # Check if we got an actual PDF or HTML
                        content = page.content()
                        if '<html' in content.lower():
                            # Still HTML, might need to trigger download
                            # Try to find and click download link
                            download_link = page.locator('a[href*=".pdf"], button:has-text("Download")')
                            if download_link.count() > 0:
                                with page.expect_download() as download_info:
                                    download_link.first.click()
                                download = download_info.value
                                
                                cache_path = self.get_pdf_cache_path(url)
                                download.save_as(cache_path)
                                content = cache_path.read_bytes()
                            else:
                                # Can't find PDF, return HTML
                                content = content.encode()
                        else:
                            # Got PDF content directly
                            content = page.content().encode()
                        
                        if content.startswith(b'%PDF'):
                            # It's a real PDF
                            cache_path = self.get_pdf_cache_path(url)
                            cache_path.write_bytes(content)
                            content_hash = self.calculate_content_hash(content)
                            text, raw_specs = self.extract_pdf_specs_with_docling(content)
                            return response.status, "pdf_text", text, content_hash, str(cache_path), raw_specs
                        else:
                            # Still HTML, process as HTML
                            content_hash = self.calculate_content_hash(content)
                            raw_specs = self.extract_all_html_specs(content.decode('utf-8', errors='ignore'))
                            return response.status, "html", content.decode('utf-8', errors='ignore'), content_hash, None, raw_specs
                    
                    else:
                        # HTML page - wait for content
                        time.sleep(3)
                        
                        # Try to wait for specific content
                        try:
                            page.wait_for_selector("table, .specifications, .specs, .datasheet, .product-specs", 
                                                 timeout=5000, state="visible")
                        except:
                            pass  # Content might be there even without these selectors
                        
                        html_content = page.content()
                        content_hash = self.calculate_content_hash(html_content.encode())
                        raw_specs = self.extract_all_html_specs(html_content)
                        
                        return response.status, "html", html_content, content_hash, None, raw_specs
                        
                finally:
                    browser.close()
                    
        except ImportError:
            print(f"  → Playwright not available, falling back to requests")
            return self._fetch_with_requests(url)
        except Exception as e:
            print(f"  → Browser error: {e}, falling back to requests")
            return self._fetch_with_requests(url)
    
    def _fetch_with_requests(self, url: str) -> Tuple[int, str, str, str, Optional[str], Optional[dict]]:
        """
        Original fetch method using requests library.
        """
        is_pdf = url.lower().endswith(".pdf")
        
        # Fetch from network
        r = requests.get(url, timeout=30)
        content = r.content
        content_hash = self.calculate_content_hash(content)
        
        # Process content
        if is_pdf:
            # Cache the PDF
            file_path = self.cache_pdf(url, content)
            
            # Extract with Docling
            text, raw_specs = self.extract_pdf_specs_with_docling(content)
            return r.status_code, "pdf_text", text, content_hash, file_path, raw_specs
        else:
            # HTML processing
            text = r.text
            raw_specs = self.extract_all_html_specs(text)
            return r.status_code, "html", text, content_hash, None, raw_specs
    
    def fetch_with_cache(self, url: str) -> Tuple[int, str, str, str, Optional[str], Optional[dict]]:
        """
        Enhanced fetch with caching, fingerprinting, and automatic browser detection.
        Returns: (status_code, content_type, text, content_hash, file_path, raw_specs)
        """
        # Check if we have a cached version
        is_pdf = url.lower().endswith(".pdf")
        
        if is_pdf:
            # Try to get from cache first
            cached_content = self.get_cached_pdf(url)
            if cached_content:
                content_hash = self.calculate_content_hash(cached_content)
                
                # Check if we should skip based on hash
                should_skip, cached_text, cached_path = self.should_skip_document(url, content_hash)
                if should_skip and cached_text:
                    print(f"  → Skipping {url} (unchanged)")
                    return 200, "pdf_text", cached_text, content_hash, cached_path, None
                
                # Process cached PDF
                print(f"  → Processing cached PDF: {url}")
                text, raw_specs = self.extract_pdf_specs_with_docling(cached_content)
                return 200, "pdf_text", text, content_hash, str(self.get_pdf_cache_path(url)), raw_specs
        
        # Fetch from network
        print(f"  → Fetching: {url}")
        r = requests.get(url, timeout=30)
        
        # Check if browser is needed
        if self.requires_browser(url, r):
            return self.fetch_with_browser(url)
        
        content = r.content
        content_hash = self.calculate_content_hash(content)
        
        # Check if content has changed
        should_skip, cached_text, cached_path = self.should_skip_document(url, content_hash)
        if should_skip and cached_text:
            print(f"  → Content unchanged, using cached data")
            return r.status_code, "pdf_text" if is_pdf else "html", cached_text, content_hash, cached_path, None
        
        # Process new content
        if is_pdf:
            # Cache the PDF
            file_path = self.cache_pdf(url, content)
            
            # Extract with Docling
            text, raw_specs = self.extract_pdf_specs_with_docling(content)
            return r.status_code, "pdf_text", text, content_hash, file_path, raw_specs
        else:
            # HTML processing
            text = r.text
            raw_specs = self.extract_all_html_specs(text)
            return r.status_code, "html", text, content_hash, None, raw_specs
    
    def store_document(self, session, target: dict, status: int, content_type: str, 
                      text: str, content_hash: str, file_path: Optional[str], 
                      raw_specs: Optional[dict]) -> bool:
        """
        Store or update document in database with proper duplicate handling.
        Returns True if document was stored/updated, False if skipped.
        """
        from ..models import RawDocument
        
        # Check if document with same URL and hash already exists
        existing_same_hash = session.query(RawDocument).filter_by(
            url=target["url"],
            content_hash=content_hash
        ).first()
        
        if existing_same_hash:
            print(f"  → Document unchanged, skipping database insert")
            return False
        
        # Check if document with same URL but different hash exists (content changed)
        existing_diff_hash = session.query(RawDocument).filter_by(
            product_id=target["product_id"],
            url=target["url"]
        ).first()
        
        if existing_diff_hash:
            # Update existing document with new content
            print(f"  → Content changed, updating existing document")
            existing_diff_hash.http_status = status
            existing_diff_hash.content_type = content_type
            existing_diff_hash.text = text[:2_000_000]
            existing_diff_hash.raw_specs = raw_specs if raw_specs else None
            existing_diff_hash.content_hash = content_hash
            existing_diff_hash.file_path = file_path
            existing_diff_hash.fetched_at = __import__('datetime').datetime.utcnow()
            return True
        
        # No existing document, create new one
        print(f"  → Storing new document")
        session.add(
            RawDocument(
                product_id=target["product_id"],
                url=target["url"],
                http_status=status,
                content_type=content_type,
                text=text[:2_000_000],
                raw_specs=raw_specs if raw_specs else None,
                content_hash=content_hash,
                file_path=file_path,
            )
        )
        return True
