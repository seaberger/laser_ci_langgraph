"""
Enhanced Lumencor scraper using Playwright for JavaScript-rendered content.

This scraper uses a headless browser to:
1. Load JavaScript-rendered product pages
2. Download dynamically-generated PDFs
3. Extract specifications from both HTML and PDF content
"""

from playwright.sync_api import sync_playwright
from .base import BaseScraper
from ..db import SessionLocal
import time
from pathlib import Path
import hashlib


class LumencorBrowserScraper(BaseScraper):
    """Enhanced scraper for Lumencor using headless browser."""
    
    def vendor(self) -> str:
        """Return vendor name."""
        return "Lumencor"
    
    def fetch_with_browser(self, url: str):
        """
        Fetch content using Playwright browser.
        Handles JavaScript-rendered pages and dynamic PDF downloads.
        """
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # Navigate to URL
                print(f"  → Browser fetching: {url}")
                response = page.goto(url, wait_until="networkidle", timeout=30000)
                
                if url.lower().endswith(".pdf"):
                    # Handle PDF download
                    # Set up download handler
                    with page.expect_download() as download_info:
                        # Click or navigate to trigger download if needed
                        page.goto(url)
                    download = download_info.value
                    
                    # Save PDF to cache
                    cache_path = self.get_pdf_cache_path(url)
                    download.save_as(cache_path)
                    
                    # Read the content
                    content = cache_path.read_bytes()
                    content_hash = self.calculate_content_hash(content)
                    
                    # Extract specs from PDF
                    text, raw_specs = self.extract_pdf_specs_with_docling(content)
                    
                    return response.status, "pdf_text", text, content_hash, str(cache_path), raw_specs
                    
                else:
                    # Handle HTML page - wait for content to load
                    # Wait a bit for JavaScript to render
                    time.sleep(3)
                    
                    # Try to find specification tables or content
                    # Look for common patterns in the rendered content
                    page.wait_for_selector("table, .specifications, .specs, .datasheet", 
                                         timeout=5000, state="visible")
                    
                    # Get the rendered HTML
                    html_content = page.content()
                    content_hash = self.calculate_content_hash(html_content.encode())
                    
                    # Extract specs from HTML
                    raw_specs = self.extract_all_html_specs(html_content)
                    
                    return response.status, "html", html_content, content_hash, None, raw_specs
                    
            except Exception as e:
                print(f"  → Browser error: {e}")
                # Fall back to basic fetch
                return self.fetch_with_cache(url)
                
            finally:
                browser.close()
    
    def run(self):
        """Run the enhanced Lumencor scraper with browser support."""
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                # Use browser for fetching
                status, content_type, text, content_hash, file_path, raw_specs = self.fetch_with_browser(tgt["url"])
                
                # Store using base class method
                self.store_document(s, tgt, status, content_type, text, 
                                  content_hash, file_path, raw_specs)
            s.commit()
        finally:
            s.close()