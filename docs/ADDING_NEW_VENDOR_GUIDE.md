# Adding a New Vendor Guide

This guide explains how to add a new laser vendor to the competitive intelligence pipeline.

## Overview

Adding a new vendor involves:
1. Configuring target products in YAML
2. Creating a unified scraper
3. Registering the scraper in the pipeline
4. Testing the implementation

## Step 1: Configure Target Products

Edit `config/target_products.yml` to add your vendor configuration:

```yaml
vendors:
  # ... existing vendors ...
  
  - name: "NewVendor"  # Vendor display name
    homepage: "https://www.newvendor.com"
    discovery_mode: "smart"  # Use 'smart' for search-based discovery
    max_products: 50  # Limit number of products to discover
    requires_browser: false  # Set true if site needs JavaScript
    
    segments:
      - id: diode_instrumentation  # or light_engines
        # Product patterns to search for
        product_patterns:
          - "ModelX"        # Product family names
          - "ModelY 532"    # Specific models
          - "SeriesZ"       # Product series
          
        # Categories to include in search results
        include_categories:
          - "laser"
          - "diode"
          - "cw"
          - "single frequency"
          
        # Categories to exclude from results
        exclude_categories:
          - "accessories"
          - "optics"
          - "filters"
          - "mounts"
```

### Configuration Options

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `name` | Yes | Vendor display name | "Thorlabs" |
| `homepage` | Yes | Company website URL | "https://thorlabs.com" |
| `discovery_mode` | No | "smart" or "static" | "smart" |
| `max_products` | No | Limit discovered products | 50 |
| `requires_browser` | No | For JavaScript-heavy sites | false |
| `product_patterns` | Yes | Product names to search | ["CPS", "CLD"] |
| `include_categories` | No | Required keywords | ["laser", "diode"] |
| `exclude_categories` | No | Excluded keywords | ["mount", "cable"] |

### Product Pattern Tips

1. **Start broad**: Use family names like "CPS" rather than specific models
2. **Add specifics**: Include key models like "CPS532" for important products
3. **Test patterns**: Search manually on vendor site first
4. **Limit patterns**: 10-20 patterns per vendor is usually sufficient

## Step 2: Create Unified Scraper

Create a new file `src/laser_ci_lg/scrapers/unified_newvendor.py`:

```python
"""
Unified scraper for NewVendor products.
"""

from .unified_base import UnifiedBaseScraper


class UnifiedNewVendorScraper(UnifiedBaseScraper):
    """Unified scraper for NewVendor with search discovery."""
    
    def vendor(self) -> str:
        """Return vendor name matching config file."""
        return "NewVendor"
    
    def __init__(self, config_path: str = "config/target_products.yml", 
                 force_refresh: bool = False):
        """Initialize with target products configuration."""
        super().__init__(config_path, force_refresh)
```

That's it! The base class handles:
- Search-based discovery via DuckDuckGo
- PDF discovery on product pages
- SHA-256 content fingerprinting
- Database storage
- Caching

### Optional: Custom Extraction

If the vendor has unusual HTML/PDF formats, override extraction:

```python
def extract_vendor_specific_specs(self, html: str) -> dict:
    """Custom extraction for vendor-specific format."""
    specs = {}
    
    # Example: Handle special table format
    if "SpecialTableClass" in html:
        # Custom parsing logic
        pass
    
    return specs
```

## Step 3: Register in Pipeline

Edit `src/laser_ci_lg/crawler_unified.py`:

### 3.1 Add Import

```python
# Add with other imports
from .scrapers.unified_newvendor import UnifiedNewVendorScraper
```

### 3.2 Add to Scraper Builder

Find the `run_unified_scrapers()` function and add:

```python
# In the vendor check section
if vendor_name == "NewVendor":
    scraper = UnifiedNewVendorScraper(config_path, force_refresh)
    scraper.run()
    scrapers_run += 1
```

## Step 4: Test Implementation

### 4.1 Test Discovery Only

```bash
# Test search-based discovery
uv run python -c "
from src.laser_ci_lg.scrapers.unified_newvendor import UnifiedNewVendorScraper
scraper = UnifiedNewVendorScraper()
scraper.load_config()
results = scraper.discover_products_smart(scraper.vendor_config['segments'][0])
print(f'Found {len(results)} products')
for r in results[:5]:
    print(f\"  - {r['name']}: {r['url']}\")
"
```

### 4.2 Run Full Scraper

```bash
# Clean any existing data
uv run python -m src.laser_ci_lg.cli clean newvendor

# Run the scraper
uv run python -m src.laser_ci_lg.cli run --scraper newvendor

# Check results
uv run python -m src.laser_ci_lg.cli list-vendors
```

### 4.3 Force Refresh (if needed)

```bash
# Bypass cache for fresh discovery
uv run python -m src.laser_ci_lg.cli run --scraper newvendor --force-refresh
```

## Step 5: Verify Results

Check that data was collected:

```bash
# Check database
sqlite3 data/laser-ci.sqlite "
SELECT m.name, COUNT(p.id) as products, COUNT(d.id) as documents
FROM manufacturers m 
LEFT JOIN products p ON m.id = p.manufacturer_id
LEFT JOIN raw_documents d ON p.id = d.product_id
WHERE m.name = 'NewVendor'
GROUP BY m.id"

# Check cached PDFs
ls -la data/pdf_cache/newvendor/
```

## Troubleshooting

### No Products Found

1. **Check search patterns**: Test manually on DuckDuckGo
   ```
   site:newvendor.com "ModelX" laser
   ```

2. **Verify domain**: Ensure homepage URL is correct
   
3. **Adjust patterns**: Make them less specific
   ```yaml
   product_patterns:
     - "laser"  # Very broad
     - "CW"     # Category search
   ```

### Wrong Products Found

1. **Add exclude categories**:
   ```yaml
   exclude_categories:
     - "accessories"
     - "replacement parts"
     - "discontinued"
   ```

2. **Refine include categories**:
   ```yaml
   include_categories:
     - "laser system"
     - "laser module"
     - "laser diode"
   ```

### JavaScript Site Issues

If products aren't loading, the site may require JavaScript:

```yaml
requires_browser: true  # Enable Playwright for this vendor
```

### Custom Extraction Needed

If specs aren't extracted properly, check HTML structure:

```bash
# Download a sample page
curl -o sample.html "https://newvendor.com/product-page"

# Examine structure
grep -i "wavelength\|power\|specification" sample.html
```

Then add custom extraction logic to your scraper.

## Example: Adding Thorlabs

Here's a complete example for Thorlabs:

### 1. Configuration

```yaml
# config/target_products.yml
- name: "Thorlabs"
  homepage: "https://www.thorlabs.com"
  discovery_mode: "smart"
  max_products: 30
  
  segments:
    - id: diode_instrumentation
      product_patterns:
        - "CPS532"      # Collimated laser diode
        - "CPS635"      
        - "CLD1015"     # Compact laser diode
        - "L405"        # Laser diode modules
        - "L520"
        - "L785"
        
      include_categories:
        - "laser diode"
        - "cw laser"
        - "single mode"
        
      exclude_categories:
        - "mount"
        - "driver"
        - "cable"
        - "lens"
```

### 2. Scraper

```python
# src/laser_ci_lg/scrapers/unified_thorlabs.py
from .unified_base import UnifiedBaseScraper

class UnifiedThorlabsScraper(UnifiedBaseScraper):
    def vendor(self) -> str:
        return "Thorlabs"
    
    def __init__(self, config_path: str = "config/target_products.yml", 
                 force_refresh: bool = False):
        super().__init__(config_path, force_refresh)
```

### 3. Register

```python
# crawler_unified.py
from .scrapers.unified_thorlabs import UnifiedThorlabsScraper

# In run_unified_scrapers()
if vendor_name == "Thorlabs":
    scraper = UnifiedThorlabsScraper(config_path, force_refresh)
    scraper.run()
```

### 4. Test

```bash
uv run python -m src.laser_ci_lg.cli run --scraper thorlabs
```

## Best Practices

1. **Start Small**: Begin with 5-10 product patterns
2. **Test Incrementally**: Verify discovery before adding more patterns
3. **Use Rate Limiting**: The system includes delays, don't bypass them
4. **Cache Wisely**: Use `--force-refresh` sparingly
5. **Document Quirks**: Add comments for vendor-specific behavior

## Summary

Adding a new vendor is straightforward:
1. Configure products in `target_products.yml`
2. Create minimal unified scraper
3. Register in crawler
4. Test and refine patterns

The unified base scraper handles all the complex work:
- Search-based discovery
- PDF finding and caching
- Content fingerprinting
- Database storage
- Extraction (with optional customization)

Most vendors can be added with just configuration and a 10-line scraper class!