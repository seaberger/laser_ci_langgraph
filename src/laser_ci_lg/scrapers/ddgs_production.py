"""
Production-ready DuckDuckGo discovery for the laser CI pipeline.
Simple, robust, and efficient.
"""

import time
import json
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from pathlib import Path
from ddgs import DDGS

from ..db import SessionLocal
from ..models import Manufacturer, Product, RawDocument


class ProductionDDGSDiscovery:
    """
    Production DuckDuckGo discovery with proper error handling and limits.
    """
    
    def __init__(self, 
                 max_products_per_vendor: int = 30,
                 max_patterns_per_vendor: int = 10,
                 delay_between_searches: float = 1.0):
        """
        Initialize with sensible defaults.
        
        Args:
            max_products_per_vendor: Maximum products to discover per vendor
            max_patterns_per_vendor: Maximum patterns to search per vendor
            delay_between_searches: Delay in seconds between searches
        """
        self.max_products_per_vendor = max_products_per_vendor
        self.max_patterns_per_vendor = max_patterns_per_vendor
        self.delay_between_searches = delay_between_searches
        self.ddgs = DDGS(timeout=20)
        
    def discover_vendor(self, vendor_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Discover products for a single vendor.
        
        Args:
            vendor_config: Vendor configuration from target_products.yml
            
        Returns:
            List of discovered products
        """
        vendor_name = vendor_config.get("name", "Unknown")
        homepage = vendor_config.get("homepage", "")
        
        # Extract domain
        domain = urlparse(homepage).netloc
        if not domain:
            print(f"  ❌ No domain for {vendor_name}")
            return []
        
        print(f"\n🔍 Discovering {vendor_name}")
        print(f"   Domain: {domain}")
        
        # Collect patterns (limited)
        all_patterns = []
        for segment in vendor_config.get("segments", []):
            patterns = segment.get("product_patterns", [])
            all_patterns.extend(patterns)
        
        # Apply limits
        all_patterns = all_patterns[:self.max_patterns_per_vendor]
        
        print(f"   Searching {len(all_patterns)} patterns")
        
        discovered_products = []
        discovered_urls = set()
        
        # Search each pattern
        for i, pattern in enumerate(all_patterns, 1):
            if len(discovered_products) >= self.max_products_per_vendor:
                print(f"   📊 Reached limit of {self.max_products_per_vendor} products")
                break
            
            print(f"   [{i}/{len(all_patterns)}] {pattern}...", end="")
            
            # Build query
            query = f'site:{domain} "{pattern}" laser'
            
            try:
                # Search with limited results
                results = self.ddgs.text(
                    query,
                    region='wt-wt',
                    safesearch='off',
                    max_results=5
                )
                
                found = 0
                for result in results:
                    url = result.get('href', '')
                    title = result.get('title', '')
                    
                    # Skip duplicates
                    if url in discovered_urls:
                        continue
                    
                    # Check if it's a product page
                    if self.is_product_page(url, title):
                        discovered_urls.add(url)
                        
                        product = {
                            'vendor': vendor_name,
                            'pattern': pattern,
                            'name': self.clean_product_name(title, pattern),
                            'url': url,
                            'segment_id': self.get_segment_id(vendor_config, pattern)
                        }
                        
                        discovered_products.append(product)
                        found += 1
                        
                        if len(discovered_products) >= self.max_products_per_vendor:
                            break
                
                if found > 0:
                    print(f" ✓ ({found} products)")
                else:
                    print(f" ⚠️")
                    
            except Exception as e:
                print(f" ❌ {str(e)[:30]}")
            
            # Rate limiting
            time.sleep(self.delay_between_searches)
        
        print(f"   Total: {len(discovered_products)} products discovered")
        return discovered_products
    
    def is_product_page(self, url: str, title: str) -> bool:
        """Check if URL/title indicates a product page."""
        combined = f"{url.lower()} {title.lower()}"
        
        # Positive indicators
        if any(x in combined for x in ['laser', 'product', '/obis', '/genesis', '/sapphire']):
            # Negative indicators
            if not any(x in combined for x in ['blog', 'news', 'career', 'press']):
                return True
        
        return False
    
    def clean_product_name(self, title: str, pattern: str) -> str:
        """Extract clean product name from title."""
        # Remove common suffixes
        title = title.split(' | ')[0]
        title = title.split(' - ')[0]
        
        # If pattern is prominent, use it
        if pattern.lower() in title.lower():
            # Extract the part with the pattern
            words = title.split()
            for i, word in enumerate(words):
                if pattern.lower() in word.lower():
                    start = max(0, i - 1)
                    end = min(len(words), i + 3)
                    return ' '.join(words[start:end])
        
        return title[:60]  # Fallback to truncated title
    
    def get_segment_id(self, vendor_config: Dict, pattern: str) -> str:
        """Determine segment ID for a pattern."""
        for segment in vendor_config.get("segments", []):
            if pattern in segment.get("product_patterns", []):
                return segment.get("id", "unknown")
        return "diode_instrumentation"  # Default
    
    def discover_all_vendors(self, config_path: str = "config/target_products.yml") -> List[Dict[str, Any]]:
        """
        Discover products for all vendors.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            List of all discovered products
        """
        from ruamel.yaml import YAML
        
        print("\n" + "="*60)
        print("Production DuckDuckGo Discovery")
        print("="*60)
        
        yaml = YAML(typ="safe")
        with open(config_path) as f:
            cfg = yaml.load(f)
        
        all_products = []
        
        for vendor_config in cfg.get("vendors", []):
            vendor_products = self.discover_vendor(vendor_config)
            all_products.extend(vendor_products)
        
        # Summary
        print("\n" + "="*60)
        print("Discovery Summary")
        print("="*60)
        
        # Group by vendor
        by_vendor = {}
        for prod in all_products:
            vendor = prod['vendor']
            if vendor not in by_vendor:
                by_vendor[vendor] = []
            by_vendor[vendor].append(prod)
        
        for vendor, products in by_vendor.items():
            print(f"  {vendor}: {len(products)} products")
        
        print(f"\nTotal: {len(all_products)} products discovered")
        
        return all_products
    
    def store_in_database(self, products: List[Dict[str, Any]], config_path: str = "config/target_products.yml"):
        """
        Store discovered products in database.
        
        Args:
            products: List of discovered products
            config_path: Path to configuration for homepage URLs
        """
        from ruamel.yaml import YAML
        
        print("\n📀 Storing in database...")
        
        yaml = YAML(typ="safe")
        with open(config_path) as f:
            cfg = yaml.load(f)
        
        # Build vendor homepage map
        vendor_homepages = {}
        for vendor in cfg.get("vendors", []):
            vendor_homepages[vendor["name"]] = vendor.get("homepage", "")
        
        s = SessionLocal()
        
        try:
            # Group products by vendor
            by_vendor = {}
            for prod in products:
                vendor = prod['vendor']
                if vendor not in by_vendor:
                    by_vendor[vendor] = []
                by_vendor[vendor].append(prod)
            
            # Process each vendor
            for vendor_name, vendor_products in by_vendor.items():
                # Get or create manufacturer
                manufacturer = s.query(Manufacturer).filter_by(name=vendor_name).first()
                if not manufacturer:
                    manufacturer = Manufacturer(
                        name=vendor_name,
                        homepage=vendor_homepages.get(vendor_name, "")
                    )
                    s.add(manufacturer)
                    s.flush()
                
                # Process products
                for prod_data in vendor_products:
                    # Get or create product
                    product = s.query(Product).filter_by(
                        manufacturer_id=manufacturer.id,
                        name=prod_data['name']
                    ).first()
                    
                    if not product:
                        product = Product(
                            manufacturer_id=manufacturer.id,
                            name=prod_data['name'],
                            segment_id=prod_data['segment_id'],
                            product_url=prod_data['url']
                        )
                        s.add(product)
                        s.flush()
                    
                    # Create document placeholder
                    existing = s.query(RawDocument).filter_by(
                        product_id=product.id,
                        url=prod_data['url']
                    ).first()
                    
                    if not existing:
                        doc = RawDocument(
                            product_id=product.id,
                            url=prod_data['url'],
                            content_type='product_page',
                            text="",  # To be fetched later
                            raw_specs={},
                            content_hash=""
                        )
                        s.add(doc)
            
            s.commit()
            print(f"  ✓ Stored {len(products)} products in database")
            
        except Exception as e:
            print(f"  ❌ Database error: {e}")
            s.rollback()
        finally:
            s.close()


def run_production_discovery():
    """
    Run production discovery with all vendors.
    """
    from ..db import bootstrap_db
    
    # Initialize database
    bootstrap_db()
    
    # Create discovery with production settings
    discovery = ProductionDDGSDiscovery(
        max_products_per_vendor=20,  # Reasonable limit
        max_patterns_per_vendor=10,  # Focus on key patterns
        delay_between_searches=1.5  # Conservative rate limiting
    )
    
    # Discover all vendors
    products = discovery.discover_all_vendors()
    
    # Store in database
    if products:
        discovery.store_in_database(products)
    
    return len(products)


if __name__ == "__main__":
    total = run_production_discovery()
    print(f"\n✅ Discovery complete: {total} total products")