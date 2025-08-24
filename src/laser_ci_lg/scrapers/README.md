# Scraper Development Guide

This guide explains how to create a new scraper for the Laser CI system based on the patterns established in existing scrapers.

## Overview

Scrapers are responsible for fetching product pages and datasheets from vendor websites, extracting specifications, and storing them in the database. All scrapers inherit from `BaseScraper` which provides common functionality.

## Scraper Structure

### Minimal Scraper Implementation

The simplest working scraper follows this pattern:

```python
from .base import BaseScraper
from ..db import SessionLocal


class VendorNameScraper(BaseScraper):
    """Scraper for VendorName products."""
    
    def vendor(self) -> str:
        """Return vendor name for display."""
        return "VendorName"
    
    def run(self):
        """Run the scraper."""
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                # Fetch with caching and extraction
                status, content_type, text, content_hash, file_path, raw_specs = self.fetch_with_cache(tgt["url"])
                
                # Store using base class method
                self.store_document(s, tgt, status, content_type, text, 
                                  content_hash, file_path, raw_specs)
            s.commit()
        finally:
            s.close()
```

## Key Components

### 1. The `vendor()` Method
- **Required**: Must return the vendor name as a string
- Used for display in CLI output

### 2. The `run()` Method
- **Required**: Main entry point for the scraper
- Handles database session management
- Iterates through targets and fetches/stores documents

### 3. The `iter_targets()` Method
- **Inherited**: Provided by BaseScraper
- Yields target dictionaries containing:
  - `product_id`: Database ID of the product
  - `url`: URL to fetch (either product page or datasheet)
  - Other metadata from config

### 4. The `fetch_with_cache()` Method
- **Inherited**: Provided by BaseScraper
- Returns tuple: `(status_code, content_type, text, content_hash, file_path, raw_specs)`
- Automatically:
  - Caches PDFs locally
  - Calculates content hashes for duplicate detection
  - Extracts specs using the extraction system
  - Handles both HTML and PDF content

### 5. The `store_document()` Method
- **Inherited**: Provided by BaseScraper
- Parameters:
  - `session`: Database session
  - `target`: Target dictionary with `product_id` and `url`
  - `status`: HTTP status code
  - `content_type`: 'html' or 'pdf_text'
  - `text`: Document text content
  - `content_hash`: SHA-256 hash of content
  - `file_path`: Local cache path (for PDFs)
  - `raw_specs`: Extracted specifications dictionary
- Handles:
  - Duplicate detection (skips unchanged documents)
  - Update detection (updates changed documents)
  - New document insertion

## Step-by-Step: Adding a New Vendor

### 1. Create the Scraper File

Create `src/laser_ci_lg/scrapers/vendorname.py`:

```python
from .base import BaseScraper
from ..db import SessionLocal


class VendorNameScraper(BaseScraper):
    def vendor(self) -> str:
        return "VendorName"
    
    def run(self):
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                status, content_type, text, content_hash, file_path, raw_specs = self.fetch_with_cache(tgt["url"])
                self.store_document(s, tgt, status, content_type, text, 
                                  content_hash, file_path, raw_specs)
            s.commit()
        finally:
            s.close()
```

### 2. Add to Configuration

Edit `config/competitors.yml`:

```yaml
  - name: VendorName
    homepage: "https://vendorname.com"
    segments:
      - id: diode_instrumentation  # or light_engines
        products:
          - name: "Product Model Name"
            product_url: "https://vendorname.com/products/model"
            datasheets:
              - "https://vendorname.com/datasheets/model.pdf"
```

### 3. Register in Crawler

Edit `src/laser_ci_lg/crawler.py`:

Add import:
```python
from .scrapers.vendorname import VendorNameScraper
```

Add to mappings (for CLI filter support):
```python
mappings = {
    # ... existing mappings ...
    'vendorname': ['vendorname'],
}
```

Add to scraper instantiation:
```python
elif v["name"] == "VendorName":
    scrapers.append(VendorNameScraper(t, force_refresh=force_refresh))
```

Update help text:
```python
print("  - vendorname")
```

### 4. Test the Scraper

```bash
# Run just your scraper
uv run python -m src.laser_ci_lg.cli run --scraper vendorname

# Check extraction results
uv run python -m src.laser_ci_lg.cli list-vendors

# Clean and re-run if needed
uv run python -m src.laser_ci_lg.cli clean vendorname
uv run python -m src.laser_ci_lg.cli run --scraper vendorname
```

## Advanced Features

### Custom Extraction Logic

If the default extraction doesn't work well for a vendor, you can override methods:

```python
class VendorNameScraper(BaseScraper):
    def extract_custom_specs(self, html_text: str) -> dict:
        """Custom extraction logic for this vendor."""
        specs = {}
        # Custom parsing logic here
        return specs
    
    def run(self):
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                if tgt["url"].endswith(".html"):
                    # Use custom extraction for HTML
                    response = requests.get(tgt["url"])
                    specs = self.extract_custom_specs(response.text)
                    # ... store document ...
                else:
                    # Use default for PDFs
                    status, content_type, text, content_hash, file_path, raw_specs = self.fetch_with_cache(tgt["url"])
                    self.store_document(s, tgt, status, content_type, text, 
                                      content_hash, file_path, raw_specs)
            s.commit()
        finally:
            s.close()
```

### Dynamic Product Discovery

Some vendors may need dynamic product discovery:

```python
class VendorNameScraper(BaseScraper):
    def discover_products(self) -> list:
        """Discover products dynamically from vendor site."""
        products = []
        # Scrape product listing page
        # Extract product URLs
        return products
    
    def run(self):
        # Custom implementation with discovered products
        pass
```

## Common Issues and Solutions

### Issue: Extraction returns 0 specs
- Check if the vendor uses unusual HTML structure
- May need custom extraction logic
- Verify URLs are correct and accessible

### Issue: PDFs not downloading
- Check if PDFs require authentication
- Verify PDF URLs are direct links, not JavaScript downloads
- May need custom headers or cookies

### Issue: Duplicate documents
- The system automatically handles duplicates via content hashing
- Documents are only re-processed if content changes

### Issue: Rate limiting
- Add delays between requests if needed:
```python
import time

for tgt in self.iter_targets():
    # ... fetch and store ...
    time.sleep(1)  # Be respectful
```

## Extraction System

The built-in extraction system (`src/laser_ci_lg/extraction.py`) provides:

### HTML Extraction
- Pandas table parsing
- BeautifulSoup parsing
- Pattern matching for technical specs
- Handles concatenated tables (Omicron fix)

### PDF Extraction
- Docling for table extraction
- Markdown table parsing
- Pattern matching for specifications
- Column alignment correction (Oxxius fix)

### Preserved Formats
- Tolerances: ±5 nm, ±0.5%
- Inequalities: ≤, ≥, <, >
- Ratios: 100:1, >50:1
- Ranges: 10-45°C, 50-100 mW
- Units: nm, mW, mm, MHz, etc.

## Best Practices

1. **Keep it simple**: Start with the minimal implementation
2. **Use inheritance**: Leverage BaseScraper methods
3. **Test incrementally**: Run and verify each step
4. **Handle errors gracefully**: Use try/except blocks
5. **Be respectful**: Don't hammer vendor servers
6. **Document quirks**: Add comments for vendor-specific logic

## Examples

Study these existing scrapers for patterns:

- **Simple**: `omicron_luxx.py` - Minimal implementation
- **Standard**: `coherent.py` - Typical scraper
- **Complex**: `hubner_cobolt.py` - Custom logic

## Support

If you encounter issues:
1. Check existing scrapers for similar patterns
2. Review extraction results in the database
3. Add debug logging to understand the flow
4. Update extraction.py if needed for new table formats