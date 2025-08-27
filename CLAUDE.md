# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sightline Laser CI Module - A competitive intelligence component of the Sightline suite (enterprise and SMB apps for knowledge engine, product finder, strategic marketing and competitive analysis). Built on LangGraph with OpenAI for intelligent spec normalization. 

**v2.0 Architecture** (Current):
- **Search-based Discovery**: Uses DuckDuckGo API instead of Playwright for efficient product discovery
- **Enhanced Extraction**: Cleans spec names, removes footnotes, extracts individual SKUs from product families
- **Smart Caching**: SHA-256 content fingerprinting prevents reprocessing unchanged content
- **Unified Pipeline**: All vendors use unified base scraper with optional customization
- **Parallel Processing**: Batch normalization with ThreadPoolExecutor for LLM calls

The system discovers laser products via search, extracts specs from HTML/PDFs, normalizes heterogeneous specs into a canonical schema, and benchmarks competitors against Coherent models.

## Development Commands

### Running the Pipeline
```bash
# One-time execution
uv run python -m src.laser_ci_lg.cli run

# Run specific scraper only
uv run python -m src.laser_ci_lg.cli run --scraper coherent
uv run python -m src.laser_ci_lg.cli run --scraper hubner  # or cobolt
uv run python -m src.laser_ci_lg.cli run --scraper omicron # or luxx
uv run python -m src.laser_ci_lg.cli run --scraper oxxius  # or lbx

# Force refresh (bypass cache)
uv run python -m src.laser_ci_lg.cli run --force-refresh

# Combine options
uv run python -m src.laser_ci_lg.cli run --scraper coherent --force-refresh --model gpt-4o

# Schedule monthly runs (cron format: M H DOM MON DOW)
uv run python -m src.laser_ci_lg.cli schedule --cron "3 10 1 * *"
```

### Environment Setup
```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Configure OpenAI API key in .env file
echo "OPENAI_API_KEY=sk-..." > .env
```

## Architecture

### Unified Pipeline Flow (v2.0)
The system uses a discovery-first approach with these phases:
1. **discover** - Search for products using DuckDuckGo API with vendor-specific patterns
2. **extract** - Fetch HTML/PDF documents, clean spec names, extract individual SKUs
3. **normalize** - Convert raw specs to canonical schema (heuristics first, LLM fallback)
4. **analyze** - Group by wavelength/power class for competitive analysis
5. **report** - Generate comparison matrices and strategic insights

### Key Components

**Data Models** (`models.py`):
- `Manufacturer` - Vendor companies
- `Product` - Laser models per manufacturer/segment
- `RawDocument` - Scraped HTML/PDF content with extracted k/v pairs
- `NormalizedSpec` - Canonical schema snapshots for time-series tracking

**Spec Normalization** (`normalize_batch.py` + `llm.py`):
- Extract individual models from product families (e.g., OBIS LX 375, OBIS LX 405)
- Clean spec names: remove footnotes, units, special characters
- Heuristic mapping attempts to match vendor field names to canonical schema
- Falls back to OpenAI structured JSON when <4 fields mapped
- Parallel batch processing with ThreadPoolExecutor
- LLM uses `response_format: json_schema` for guaranteed well-formed output

**Unified Scraper System** (`scrapers/unified_base.py`):
- **UnifiedBaseScraper**: Base class handling all discovery and extraction
- Smart discovery via DuckDuckGo search with product patterns
- PDF discovery on product pages
- SHA-256 content fingerprinting for change detection
- Vendor-specific scrapers need only 10 lines of code

**Configuration** (`config/`):
- `target_products.yml` - Search patterns for discovery, 98 specific laser models
- `segments.yml` - Product categories (diode_instrumentation, light_engines)

### Database Schema
SQLite database (`data/laser-ci.sqlite`) stores:
- Manufacturer and product metadata
- Raw scraped documents with timestamps
- Normalized spec snapshots for historical tracking
- Unique constraints prevent duplicate entries

**Tables:**
- `manufacturers` - Vendor/manufacturer information
  - `id`: Primary key
  - `name`: Vendor name (e.g., 'Coherent', 'Omicron', 'Hübner Photonics (Cobolt)')
  - `homepage`: Company website URL

- `products` - Laser product models
  - `id`: Primary key
  - `manufacturer_id`: Foreign key to manufacturers
  - `segment_id`: Product segment (e.g., 'diode_instrumentation')
  - `name`: Product model name
  - `product_url`: Product page URL

- `raw_documents` - Scraped HTML and PDF documents
  - `id`: Primary key
  - `product_id`: Foreign key to products
  - `url`: Document URL
  - `content_type`: 'html' or 'pdf_text'
  - `raw_specs`: JSON string containing extracted specifications
  - `content_hash`: SHA-256 hash for duplicate detection
  - `file_path`: Local cache path for PDFs

**Accessing Data:**
```bash
# Query database directly
sqlite3 data/laser-ci.sqlite

# Example: Check vendor products
sqlite3 data/laser-ci.sqlite "SELECT m.name, COUNT(p.id) FROM manufacturers m LEFT JOIN products p ON m.id = p.manufacturer_id GROUP BY m.id"

# Example: Get spec counts
sqlite3 data/laser-ci.sqlite "SELECT m.name, d.content_type, LENGTH(d.raw_specs) FROM raw_documents d JOIN products p ON d.product_id = p.id JOIN manufacturers m ON p.manufacturer_id = m.id"
```

**PDF Cache:**
PDFs are cached locally in `data/pdf_cache/<vendor_name>/`
Example: `data/pdf_cache/omicron/luxx_plus_datasheet201901.pdf`

### LLM Integration
- Uses OpenAI API with structured output (`json_schema` format)
- Loads API key from `.env` file via python-dotenv
- Model defaults to `gpt-4o-mini`, configurable via CLI or env var
- Only triggers LLM when heuristic mapping yields insufficient fields

## Unified Scraper Architecture (v2.0)

### Minimal Unified Scraper Implementation
All new scrapers should use the unified base class:

```python
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

### Key Methods from UnifiedBaseScraper
- **discover_products_smart()**: Search-based discovery using DuckDuckGo
- **discover_pdfs_on_page()**: Find PDF links on product pages
- **process_document()**: Extract specs with fingerprinting
- **run()**: Orchestrates discovery → extraction → storage

## Adding New Vendors (v2.0)

1. **Configure target products** in `config/target_products.yml`:
```yaml
vendors:
  - name: "NewVendor"
    homepage: "https://www.newvendor.com"
    discovery_mode: "smart"  # Use search-based discovery
    max_products: 50
    segments:
      - id: diode_instrumentation
        product_patterns:  # Search patterns
          - "ModelX"
          - "ModelY 532"
          - "SeriesZ"
        include_categories:  # Required keywords
          - "laser"
          - "diode"
        exclude_categories:  # Excluded keywords
          - "accessories"
          - "mounts"
```

2. **Create unified scraper** in `src/laser_ci_lg/scrapers/unified_newvendor.py`:
```python
from .unified_base import UnifiedBaseScraper

class UnifiedNewVendorScraper(UnifiedBaseScraper):
    def vendor(self) -> str:
        return "NewVendor"
    
    def __init__(self, config_path: str = "config/target_products.yml", 
                 force_refresh: bool = False):
        super().__init__(config_path, force_refresh)
```

3. **Register in unified crawler** (`src/laser_ci_lg/crawler_unified.py`):
   - Add import: `from .scrapers.unified_newvendor import UnifiedNewVendorScraper`
   - Add to run_unified_scrapers() function

4. **Test the scraper**:
```bash
# Test discovery
uv run python -m src.laser_ci_lg.cli run --scraper newvendor

# Force refresh if needed
uv run python -m src.laser_ci_lg.cli run --scraper newvendor --force-refresh
```

For detailed guide, see `docs/ADDING_NEW_VENDOR_GUIDE.md`

## Canonical Spec Schema

Core fields normalized across all vendors:
- Optical: wavelength_nm, output_power_mw, linewidth, beam quality (M²)
- Stability: rms_noise_pct, power_stability_pct
- Modulation: analog/digital frequency limits, TTL shutter
- Fiber: output availability, NA, mode field diameter
- Physical: dimensions, interfaces, warmup time
- Unmapped specs stored in `vendor_fields` JSON

## Recent Improvements (v2.0)

### Search-Based Discovery
- Replaced Playwright crawling with DuckDuckGo search API
- Queries like `site:coherent.com "OBIS" laser` find products efficiently
- Automatic PDF discovery on product pages

### Enhanced Extraction
- **Clean spec names**: Remove footnotes (¹²³), units, special characters
- **Individual SKU extraction**: Split product families into individual models
- Example: "OBIS Family" → OBIS LX 375, OBIS LX 405, OBIS LX 445

### Improved Normalization
- Parallel batch processing with ThreadPoolExecutor
- LLM fallback when heuristics map <4 fields
- OpenAI structured output guarantees valid JSON

### Smart Caching
- SHA-256 content fingerprinting prevents reprocessing
- PDF cache in `data/pdf_cache/<vendor>/`
- Discovery results cached to avoid repeated searches

## Current Development Status

**In Development** - No production metrics yet. Focus areas:
- Refining search patterns for better discovery
- Improving spec extraction accuracy
- Optimizing LLM usage for normalization
- Building comprehensive test suite

## Key Files to Know

- `config/target_products.yml` - 98 specific laser models configured
- `src/laser_ci_lg/scrapers/unified_base.py` - Core discovery/extraction logic
- `src/laser_ci_lg/normalize_batch.py` - Batch normalization with LLM
- `src/laser_ci_lg/extraction.py` - Spec cleaning and SKU extraction
- `docs/ADDING_NEW_VENDOR_GUIDE.md` - Complete vendor addition guide

## Monthly Reporting

Reports include:
- New products detected since last run
- Spec changes (power increases, new wavelengths, etc.)
- Benchmark tables comparing similar products (e.g., 488nm @ 100mW class)
- Stored in `reports/` directory with timestamp