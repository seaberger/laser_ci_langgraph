"""
DuckDuckGo-based discovery for vendor products and PDFs.
Uses duckduckgo-search library for more reliable search without rate limiting issues.
"""

import time
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urljoin
import hashlib
from pathlib import Path
from ddgs import DDGS

from ..db import SessionLocal
from ..models import Manufacturer, Product, RawDocument


class DuckDuckGoDiscovery:
    """
    Discover vendor products using DuckDuckGo search.
    More reliable than Google scraping, no API key required.
    """
    
    def __init__(self, force_refresh: bool = False):
        """Initialize DuckDuckGo discovery."""
        self.force_refresh = force_refresh
        self.discovered_urls: Set[str] = set()
        self.cache_dir = Path("data/pdf_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ddgs = DDGS()
    
    def search_vendor_products(self, 
                              vendor_name: str,
                              domain: str, 
                              product_patterns: List[str],
                              max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search for vendor products using DuckDuckGo.
        
        Args:
            vendor_name: Name of the vendor
            domain: Domain to search (e.g., coherent.com)
            product_patterns: Product names/patterns to search for
            max_results: Maximum number of results to return
            
        Returns:
            List of discovered products with URLs
        """
        discovered = []
        processed_urls = set()
        
        print(f"\n🦆 DuckDuckGo search for {vendor_name} ({domain})")
        
        # Search for each product pattern
        for pattern in product_patterns[:20]:  # Limit patterns to be reasonable
            if len(discovered) >= max_results:
                break
            
            # Build search query for product pages
            query = f'site:{domain} "{pattern}" laser product'
            
            print(f"  Searching: {pattern}...")
            
            try:
                # Use DuckDuckGo search
                results = list(self.ddgs.text(
                    query,
                    region='wt-wt',
                    safesearch='off',
                    max_results=10
                ))
                
                for result in results:
                    url = result.get('href', '')
                    title = result.get('title', '')
                    
                    if not url or url in processed_urls:
                        continue
                    
                    processed_urls.add(url)
                    
                    # Filter for product-related URLs
                    if self.is_product_url(url, title):
                        product = {
                            'name': self.extract_product_name(title, pattern),
                            'url': url,
                            'pdfs': []
                        }
                        
                        # Search for related PDFs
                        pdf_results = self.search_pdfs(domain, pattern)
                        product['pdfs'] = pdf_results
                        
                        discovered.append(product)
                        print(f"    ✓ Found: {product['name']}")
                        
                        if len(discovered) >= max_results:
                            break
                
                # Small delay to be respectful
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    ✗ Search error: {e}")
                continue
        
        print(f"  Total found: {len(discovered)} products")
        return discovered
    
    def search_pdfs(self, domain: str, product_name: str, max_pdfs: int = 3) -> List[str]:
        """
        Search for PDF datasheets for a specific product.
        
        Args:
            domain: Domain to search
            product_name: Product name to search for
            max_pdfs: Maximum number of PDFs to return
            
        Returns:
            List of PDF URLs
        """
        pdfs = []
        query = f'site:{domain} "{product_name}" filetype:pdf datasheet'
        
        try:
            results = list(self.ddgs.text(
                query,
                region='wt-wt',
                safesearch='off',
                max_results=5
            ))
            
            for result in results:
                url = result.get('href', '')
                if url.lower().endswith('.pdf'):
                    pdfs.append(url)
                    if len(pdfs) >= max_pdfs:
                        break
        except:
            pass
        
        return pdfs
    
    def is_product_url(self, url: str, title: str = "") -> bool:
        """
        Check if URL likely points to a product page.
        
        Args:
            url: URL to check
            title: Page title (optional)
            
        Returns:
            True if URL appears to be a product page
        """
        url_lower = url.lower()
        title_lower = title.lower() if title else ""
        combined = f"{url_lower} {title_lower}"
        
        # Positive indicators
        product_indicators = [
            'product', 'laser', 'system', 'specification',
            'datasheet', 'technical', 'model', 'series'
        ]
        
        # Negative indicators
        exclude_indicators = [
            'blog', 'news', 'about', 'contact',
            'career', 'support', 'company', 'investor',
            'press', 'release', 'article'
        ]
        
        # Check for positive indicators
        has_positive = any(ind in combined for ind in product_indicators)
        
        # Check for negative indicators
        has_negative = any(ex in combined for ex in exclude_indicators)
        
        return has_positive and not has_negative
    
    def extract_product_name(self, title: str, pattern: str) -> str:
        """Extract product name from page title."""
        # Clean up title
        title_clean = title.replace(' - ', ' ').replace(' | ', ' ')
        
        # If pattern is in title, use it
        if pattern.lower() in title_clean.lower():
            # Try to extract the specific product mention
            words = title_clean.split()
            for i, word in enumerate(words):
                if pattern.lower() in word.lower():
                    # Get surrounding context
                    start = max(0, i - 1)
                    end = min(len(words), i + 3)
                    return ' '.join(words[start:end])
        
        # Otherwise use cleaned title (first part)
        parts = title_clean.split()[:5]  # First 5 words
        return ' '.join(parts)
    
    def discover_all_vendors(self, config_path: str = "config/target_products.yml") -> Dict[str, List[Dict]]:
        """
        Discover products for all vendors in configuration.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Dictionary mapping vendor names to discovered products
        """
        from ruamel.yaml import YAML
        
        yaml = YAML(typ="safe")
        with open(config_path) as f:
            cfg = yaml.load(f)
        
        all_discoveries = {}
        
        for vendor_cfg in cfg.get("vendors", []):
            vendor_name = vendor_cfg.get("name", "Unknown")
            homepage = vendor_cfg.get("homepage", "")
            max_products = vendor_cfg.get("max_products", 50)
            
            # Extract domain
            domain = urlparse(homepage).netloc
            if not domain:
                print(f"Skipping {vendor_name}: No domain found")
                continue
            
            # Collect all product patterns
            all_patterns = []
            for segment in vendor_cfg.get("segments", []):
                patterns = segment.get("product_patterns", [])
                all_patterns.extend(patterns)
            
            if not all_patterns:
                print(f"Skipping {vendor_name}: No product patterns")
                continue
            
            # Discover products
            discovered = self.search_vendor_products(
                vendor_name=vendor_name,
                domain=domain,
                product_patterns=all_patterns,
                max_results=max_products
            )
            
            all_discoveries[vendor_name] = discovered
        
        return all_discoveries


class DuckDuckGoScraper:
    """
    Scraper using DuckDuckGo search for discovery.
    Integrates with existing database and extraction pipeline.
    """
    
    def __init__(self, vendor_name: str, config_path: str = "config/target_products.yml", 
                 force_refresh: bool = False):
        """Initialize DuckDuckGo-based scraper."""
        self.vendor_name = vendor_name
        self.config_path = config_path
        self.force_refresh = force_refresh
        self.discovery = DuckDuckGoDiscovery(force_refresh)
        
        # Load vendor configuration
        self.load_config()
    
    def load_config(self):
        """Load vendor configuration from YAML."""
        from ruamel.yaml import YAML
        
        yaml = YAML(typ="safe")
        with open(self.config_path) as f:
            cfg = yaml.load(f)
        
        # Find vendor config
        self.vendor_config = None
        for vendor_cfg in cfg.get("vendors", []):
            if vendor_cfg["name"] == self.vendor_name:
                self.vendor_config = vendor_cfg
                break
        
        if not self.vendor_config:
            raise ValueError(f"No configuration found for vendor: {self.vendor_name}")
        
        self.homepage = self.vendor_config.get("homepage", "")
        self.max_products = self.vendor_config.get("max_products", 50)
    
    def run(self):
        """Run DuckDuckGo-based discovery and store in database."""
        print(f"\n{'='*60}")
        print(f"DuckDuckGo Scraper: {self.vendor_name}")
        print(f"{'='*60}")
        
        # Extract domain
        domain = urlparse(self.homepage).netloc
        if not domain:
            print(f"Error: Cannot extract domain from {self.homepage}")
            return 0
        
        # Collect all product patterns
        all_patterns = []
        segment_map = {}  # Map patterns to segments
        
        for segment in self.vendor_config.get("segments", []):
            segment_id = segment.get("id", "unknown")
            patterns = segment.get("product_patterns", [])
            
            for pattern in patterns:
                all_patterns.append(pattern)
                segment_map[pattern] = segment_id
        
        # Discover products
        discovered = self.discovery.search_vendor_products(
            vendor_name=self.vendor_name,
            domain=domain,
            product_patterns=all_patterns,
            max_results=self.max_products
        )
        
        # Store in database
        self.store_discoveries(discovered, segment_map)
        
        print(f"\n✓ Completed {self.vendor_name} discovery")
        return len(discovered)
    
    def store_discoveries(self, discoveries: List[Dict], segment_map: Dict[str, str]):
        """Store discovered products in database."""
        s = SessionLocal()
        
        try:
            # Get or create manufacturer
            manufacturer = s.query(Manufacturer).filter_by(name=self.vendor_name).first()
            if not manufacturer:
                manufacturer = Manufacturer(name=self.vendor_name, homepage=self.homepage)
                s.add(manufacturer)
                s.flush()
            
            # Process each discovery
            for disc in discoveries:
                # Determine segment
                product_name = disc['name']
                segment_id = "unknown"
                
                # Find best matching pattern for segment assignment
                for pattern, seg_id in segment_map.items():
                    if pattern.lower() in product_name.lower():
                        segment_id = seg_id
                        break
                
                # Get or create product
                product = s.query(Product).filter_by(
                    manufacturer_id=manufacturer.id,
                    name=product_name
                ).first()
                
                if not product:
                    product = Product(
                        manufacturer_id=manufacturer.id,
                        name=product_name,
                        segment_id=segment_id,
                        product_url=disc['url']
                    )
                    s.add(product)
                    s.flush()
                    print(f"    + Added product: {product_name}")
                
                # Store product page as document (placeholder for now)
                existing = s.query(RawDocument).filter_by(
                    product_id=product.id,
                    url=disc['url']
                ).first()
                
                if not existing:
                    doc = RawDocument(
                        product_id=product.id,
                        url=disc['url'],
                        content_type='product_page',
                        text="",  # Will be populated when fetched
                        raw_specs={},
                        content_hash=""  # Will be calculated when fetched
                    )
                    s.add(doc)
                
                # Store PDF references
                for pdf_url in disc.get('pdfs', []):
                    existing_pdf = s.query(RawDocument).filter_by(
                        product_id=product.id,
                        url=pdf_url
                    ).first()
                    
                    if not existing_pdf:
                        pdf_doc = RawDocument(
                            product_id=product.id,
                            url=pdf_url,
                            content_type='pdf',
                            text="",
                            raw_specs={},
                            content_hash=""
                        )
                        s.add(pdf_doc)
            
            s.commit()
            print(f"  ✓ Stored {len(discoveries)} products in database")
            
        except Exception as e:
            print(f"  ✗ Database error: {e}")
            s.rollback()
        finally:
            s.close()


def test_duckduckgo_discovery():
    """Test DuckDuckGo discovery with multiple vendors."""
    from ..db import bootstrap_db
    
    # Initialize database
    bootstrap_db()
    
    # Test with each vendor
    vendors = ["Coherent", "Omicron", "Oxxius"]
    
    total_discovered = 0
    for vendor in vendors:
        try:
            scraper = DuckDuckGoScraper(vendor, force_refresh=False)
            num_products = scraper.run()
            total_discovered += num_products
        except Exception as e:
            print(f"Error with {vendor}: {e}")
    
    print(f"\n📊 Total Summary: Discovered {total_discovered} products across {len(vendors)} vendors")
    
    # Show database statistics
    s = SessionLocal()
    try:
        product_count = s.query(Product).count()
        doc_count = s.query(RawDocument).count()
        print(f"  Database: {product_count} products, {doc_count} documents")
    finally:
        s.close()


if __name__ == "__main__":
    test_duckduckgo_discovery()