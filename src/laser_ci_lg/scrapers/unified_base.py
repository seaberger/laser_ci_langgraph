"""
Unified base scraper that combines smart discovery with static URLs.
Maintains SHA-256 fingerprinting and supports both discovery modes.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import re
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright, Page
import requests
from ..db import SessionLocal
from ..models import Manufacturer, Product, RawDocument
from ..extraction import AdvancedHTMLExtractor, AdvancedPDFExtractor
from ruamel.yaml import YAML


class UnifiedBaseScraper(ABC):
    """
    Unified scraper that supports both smart discovery and static URLs.
    Maintains SHA-256 fingerprinting for all content.
    """
    
    def __init__(self, config_path: str = "config/target_products.yml", force_refresh: bool = False):
        """Initialize unified scraper with configuration."""
        self.config_path = config_path
        self.force_refresh = force_refresh
        self.cache_dir = Path("data/pdf_cache")
        
        # Load configuration
        self.load_config()
        
        # Initialize extractors
        self.html_extractor = AdvancedHTMLExtractor()
        self.pdf_extractor = AdvancedPDFExtractor()
        
        # Track discovered content
        self.discovered_products = []
        self.processed_urls = set()
    
    @abstractmethod
    def vendor(self) -> str:
        """Return vendor name."""
        pass
    
    def load_config(self):
        """Load vendor configuration from YAML."""
        yaml = YAML(typ="safe")
        with open(self.config_path) as f:
            cfg = yaml.load(f)
        
        # Find this vendor's configuration
        self.vendor_config = None
        for vendor_cfg in cfg.get("vendors", []):
            if vendor_cfg["name"] == self.vendor():
                self.vendor_config = vendor_cfg
                break
        
        if not self.vendor_config:
            raise ValueError(f"No configuration found for vendor: {self.vendor()}")
        
        # Extract settings
        self.homepage = self.vendor_config.get("homepage", "")
        self.discovery_mode = self.vendor_config.get("discovery_mode", "static")
        self.max_products = self.vendor_config.get("max_products", None)
        self.requires_browser = self.vendor_config.get("requires_browser", False)
    
    def calculate_content_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()
    
    def should_skip_document(self, url: str, content_hash: str) -> bool:
        """
        Check if document should be skipped based on content hash.
        Returns True if document already exists with same hash.
        """
        if self.force_refresh:
            return False
        
        s = SessionLocal()
        try:
            existing = s.query(RawDocument).filter_by(
                url=url,
                content_hash=content_hash
            ).first()
            
            if existing:
                print(f"      → Skipping (unchanged): {url[:80]}")
                return True
            
            return False
        finally:
            s.close()
    
    def discover_products_smart(self, segment_config: dict) -> List[Dict[str, Any]]:
        """
        Smart discovery of products based on patterns.
        Returns list of {name, url, pdfs} dictionaries.
        """
        discovered = []
        
        # Get discovery patterns
        patterns = segment_config.get("product_patterns", [])
        include_cats = segment_config.get("include_categories", [])
        exclude_cats = segment_config.get("exclude_categories", [])
        
        if not patterns:
            return discovered
        
        print(f"  → Smart discovery for patterns: {patterns[:3]}...")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={'width': 1920, 'height': 1080})
                page = context.new_page()
                
                # Go to homepage
                page.goto(self.homepage, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                
                # Search for each pattern
                for pattern in patterns:
                    if self.max_products and len(discovered) >= self.max_products:
                        break
                    
                    # Try site search first
                    products = self.search_for_pattern(page, pattern, include_cats, exclude_cats)
                    
                    # Then browse categories
                    if len(products) < 3:
                        products.extend(self.browse_for_pattern(page, pattern, include_cats, exclude_cats))
                    
                    discovered.extend(products)
                
                browser.close()
                
        except Exception as e:
            print(f"    Smart discovery error: {e}")
        
        # Deduplicate
        seen_urls = set()
        unique = []
        for product in discovered:
            if product['url'] not in seen_urls:
                seen_urls.add(product['url'])
                unique.append(product)
        
        return unique[:self.max_products] if self.max_products else unique
    
    def search_for_pattern(self, page: Page, pattern: str, include_cats: List[str], exclude_cats: List[str]) -> List[Dict]:
        """Search for a product pattern using site search."""
        products = []
        
        # Find search box
        search_selectors = [
            'input[type="search"]',
            'input[placeholder*="search" i]',
            'input[name*="search" i]',
            'input[id*="search" i]'
        ]
        
        for selector in search_selectors:
            try:
                search_box = page.locator(selector).first
                if search_box.is_visible(timeout=1000):
                    search_box.clear()
                    search_box.fill(pattern)
                    search_box.press("Enter")
                    page.wait_for_timeout(2000)  # Reduced timeout
                    
                    # Extract product links from results
                    links = page.locator('a[href]').all()
                    for link in links[:30]:
                        try:
                            href = link.get_attribute('href')
                            # Use text_content which is faster than inner_text
                            text = link.text_content(timeout=100)
                            if text:
                                text = text.strip()
                            
                            if href and self.is_relevant_product(href, text, pattern, include_cats, exclude_cats):
                                full_url = urljoin(page.url, href)
                                products.append({
                                    'name': text if text else pattern,
                                    'url': full_url,
                                    'pdfs': []
                                })
                        except:
                            continue
                    break
            except:
                continue
        
        return products
    
    def browse_for_pattern(self, page: Page, pattern: str, include_cats: List[str], exclude_cats: List[str]) -> List[Dict]:
        """Browse categories looking for pattern."""
        products = []
        
        # Navigate to relevant category pages
        category_links = page.locator('a[href*="laser"], a[href*="product"]').all()
        
        for cat_link in category_links[:5]:
            try:
                cat_href = cat_link.get_attribute('href')
                cat_text = cat_link.text_content(timeout=100)
                if cat_text:
                    cat_text = cat_text.strip().lower()
                else:
                    continue
                
                # Check if category is relevant
                if any(inc in cat_text for inc in include_cats):
                    cat_link.click()
                    page.wait_for_timeout(2000)
                    
                    # Look for products matching pattern
                    prod_links = page.locator('a[href]').all()
                    for link in prod_links[:30]:
                        try:
                            href = link.get_attribute('href')
                            # Use text_content which is faster than inner_text
                            text = link.text_content(timeout=100)
                            if text:
                                text = text.strip()
                            
                            if href and pattern.lower() in text.lower():
                                full_url = urljoin(page.url, href)
                                products.append({
                                    'name': text,
                                    'url': full_url,
                                    'pdfs': []
                                })
                        except:
                            continue
                    
                    # Go back
                    page.go_back()
            except:
                continue
        
        return products
    
    def is_relevant_product(self, url: str, text: str, pattern: str, include_cats: List[str], exclude_cats: List[str]) -> bool:
        """Check if a URL/text represents a relevant product."""
        combined = f"{url.lower()} {text.lower()}"
        
        # Check exclusions
        for exclude in exclude_cats:
            if exclude.lower() in combined:
                return False
        
        # Check if pattern matches
        if pattern.lower() not in combined:
            return False
        
        # Check for product indicators
        product_indicators = ['/product', '/laser', '/system', '-engine']
        if not any(ind in url.lower() for ind in product_indicators):
            return False
        
        return True
    
    def discover_pdfs(self, product_url: str) -> List[str]:
        """Discover PDF URLs on a product page."""
        pdfs = []
        
        try:
            if self.requires_browser:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    page.goto(product_url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(2000)
                    
                    # Find PDF links
                    pdf_links = page.locator('a[href*=".pdf"], a:has-text("datasheet"), a:has-text("download")').all()
                    
                    for link in pdf_links[:5]:
                        try:
                            href = link.get_attribute('href')
                            if href:
                                pdfs.append(urljoin(product_url, href))
                        except:
                            continue
                    
                    browser.close()
            else:
                # Use regular requests
                response = requests.get(product_url, timeout=10)
                if response.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if '.pdf' in href.lower():
                            pdfs.append(urljoin(product_url, href))
        except:
            pass
        
        return pdfs
    
    def fetch_and_store(self, session, product: Product, url: str, content_type: str = None):
        """
        Fetch a URL and store in database with SHA-256 checking.
        """
        print(f"    → Fetching: {url[:80]}...")
        
        try:
            # Fetch content
            if self.requires_browser and content_type != 'pdf':
                # Use browser for JavaScript-heavy sites
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)
                    content = page.content().encode()
                    browser.close()
            else:
                # Use regular requests
                response = requests.get(url, timeout=30)
                if response.status_code != 200:
                    print(f"      ✗ Failed: {response.status_code}")
                    return
                content = response.content
            
            # Calculate hash
            content_hash = self.calculate_content_hash(content)
            
            # Check if should skip
            if self.should_skip_document(url, content_hash):
                return
            
            # Determine content type
            is_pdf = url.lower().endswith('.pdf') or content.startswith(b'%PDF')
            
            if is_pdf:
                # Cache PDF
                cache_dir = self.cache_dir / self.vendor().lower()
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                pdf_name = re.sub(r'[^\w\-_\.]', '_', Path(url).stem) + '.pdf'
                cache_path = cache_dir / pdf_name
                cache_path.write_bytes(content)
                
                # Extract specs
                text, specs = self.pdf_extractor.extract_specs(content)
                
                # Store or update
                existing = session.query(RawDocument).filter_by(
                    product_id=product.id,
                    url=url
                ).first()
                
                if existing:
                    existing.text = text[:1000000]
                    existing.raw_specs = specs
                    existing.content_hash = content_hash
                    existing.file_path = str(cache_path)
                else:
                    doc = RawDocument(
                        product_id=product.id,
                        url=url,
                        content_type='pdf_text',
                        text=text[:1000000],
                        raw_specs=specs,
                        content_hash=content_hash,
                        file_path=str(cache_path)
                    )
                    session.add(doc)
                
                print(f"      ✓ PDF: {len(specs)} specs")
            else:
                # HTML content
                html_content = content.decode('utf-8', errors='ignore')
                specs = self.html_extractor.extract_all_specs(html_content)
                
                # Store or update
                existing = session.query(RawDocument).filter_by(
                    product_id=product.id,
                    url=url
                ).first()
                
                if existing:
                    existing.text = html_content[:1000000]
                    existing.raw_specs = specs
                    existing.content_hash = content_hash
                else:
                    doc = RawDocument(
                        product_id=product.id,
                        url=url,
                        content_type='html',
                        text=html_content[:1000000],
                        raw_specs=specs,
                        content_hash=content_hash
                    )
                    session.add(doc)
                
                print(f"      ✓ HTML: {len(specs)} specs")
                
        except Exception as e:
            print(f"      ✗ Error: {e}")
    
    def run(self):
        """
        Main run method that combines smart discovery with static fallbacks.
        """
        print(f"\n{self.vendor()} Unified Scraper")
        print("="*60)
        print(f"  Mode: {self.discovery_mode}")
        
        s = SessionLocal()
        
        try:
            # Get or create manufacturer
            manufacturer = s.query(Manufacturer).filter_by(name=self.vendor()).first()
            if not manufacturer:
                manufacturer = Manufacturer(name=self.vendor(), homepage=self.homepage)
                s.add(manufacturer)
                s.flush()
            
            # Process each segment
            for segment in self.vendor_config.get("segments", []):
                segment_id = segment.get("id", "unknown")
                print(f"\n  Segment: {segment_id}")
                
                all_products = []
                
                # Smart discovery if enabled
                if self.discovery_mode == "smart":
                    discovered = self.discover_products_smart(segment)
                    if discovered:
                        print(f"    ✓ Discovered {len(discovered)} products")
                        all_products.extend(discovered)
                
                # Add static products as fallback or primary
                static_products = segment.get("static_products", [])
                for static_prod in static_products:
                    # Check if already discovered
                    if not any(p['url'] == static_prod.get('product_url') for p in all_products if 'url' in p):
                        all_products.append({
                            'name': static_prod['name'],
                            'url': static_prod.get('product_url'),
                            'pdfs': static_prod.get('datasheets', [])
                        })
                
                # Process all products
                for prod_data in all_products:
                    if not prod_data.get('url'):
                        continue
                    
                    # Get or create product in DB
                    product = s.query(Product).filter_by(
                        manufacturer_id=manufacturer.id,
                        name=prod_data['name']
                    ).first()
                    
                    if not product:
                        product = Product(
                            manufacturer_id=manufacturer.id,
                            name=prod_data['name'],
                            segment_id=segment_id,
                            product_url=prod_data.get('url')
                        )
                        s.add(product)
                        s.flush()
                    
                    print(f"\n  Processing: {product.name}")
                    
                    # Fetch product page
                    self.fetch_and_store(s, product, prod_data['url'])
                    
                    # Discover PDFs if not provided
                    if not prod_data.get('pdfs'):
                        prod_data['pdfs'] = self.discover_pdfs(prod_data['url'])
                    
                    # Fetch PDFs
                    for pdf_url in prod_data.get('pdfs', [])[:3]:  # Limit PDFs
                        if isinstance(pdf_url, dict):
                            pdf_url = pdf_url.get('url', pdf_url)
                        self.fetch_and_store(s, product, pdf_url, 'pdf')
            
            s.commit()
            print(f"\n✓ {self.vendor()} scraping complete")
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            s.rollback()
        finally:
            s.close()