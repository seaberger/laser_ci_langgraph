# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Laser CI (Competitive Intelligence) - An automated pipeline for monitoring laser manufacturer specifications, built on LangGraph with OpenAI for intelligent spec normalization. The system crawls manufacturer sites for diode/instrumentation lasers and light engines, normalizes heterogeneous specs into a canonical schema, and benchmarks competitors against Coherent models.

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

### LangGraph Pipeline Flow
The system uses a linear LangGraph state machine with these nodes:
1. **bootstrap** - Initialize SQLite DB and seed manufacturers/products from config
2. **crawl** - Fetch HTML/PDF documents from vendor sites
3. **normalize** - Convert raw specs to canonical schema (heuristics first, LLM fallback)
4. **report** - Generate monthly delta reports
5. **bench** - Compare competitor specs against Coherent baselines

### Key Components

**Data Models** (`models.py`):
- `Manufacturer` - Vendor companies
- `Product` - Laser models per manufacturer/segment
- `RawDocument` - Scraped HTML/PDF content with extracted k/v pairs
- `NormalizedSpec` - Canonical schema snapshots for time-series tracking

**Spec Normalization** (`normalize.py` + `llm.py`):
- Heuristic mapping attempts to match vendor field names to canonical schema
- Falls back to OpenAI structured JSON when <4 fields mapped
- LLM uses `response_format: json_schema` for guaranteed well-formed output

**Scrapers** (`scrapers/`):
- Base scraper handles HTML/PDF fetching and text extraction
- Vendor-specific scrapers inherit from `BaseScraper`
- Add custom parsing logic per vendor as needed

**Configuration** (`config/`):
- `competitors.yml` - Vendor URLs, product links, datasheet PDFs
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

## Scraper Architecture

### Base Scraper Pattern
All scrapers inherit from `BaseScraper` which provides:
- `iter_targets()` - Yields product URLs and datasheets from config
- `fetch_with_cache()` - Fetches with caching, deduplication, and extraction
- `store_document()` - Handles database storage with duplicate detection

### Minimal Scraper Implementation
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

### Key Methods from BaseScraper
- **vendor()**: Return vendor display name (required override)
- **run()**: Main entry point for scraping (required override)
- **fetch_with_cache(url)**: Returns tuple (status, content_type, text, hash, path, specs)
  - Automatically caches PDFs to `data/pdf_cache/vendor/`
  - Calculates content hashes for duplicate detection
  - Extracts specs using HTML/PDF extraction system
- **store_document()**: Handles database storage
  - Skips unchanged documents (same hash)
  - Updates changed documents
  - Inserts new documents

## Adding New Vendors

1. **Add vendor config** to `config/competitors.yml`:
```yaml
  - name: VendorName
    homepage: "https://vendor.com"
    segments:
      - id: diode_instrumentation
        products:
          - name: "Model XYZ"
            product_url: "https://vendor.com/xyz"
            datasheets:
              - "https://vendor.com/xyz.pdf"
```

2. **Create scraper** in `src/laser_ci_lg/scrapers/vendorname.py`:
   - Copy minimal implementation pattern above
   - Use existing scrapers as reference (omicron_luxx.py is simplest)

3. **Register in crawler** (`src/laser_ci_lg/crawler.py`):
   - Add import: `from .scrapers.vendorname import VendorNameScraper`
   - Add to mappings for CLI filter support
   - Add instantiation in vendor name check

4. **Test the scraper**:
```bash
# Run just your scraper
uv run python -m src.laser_ci_lg.cli run --scraper vendorname

# Clean and re-run if needed
uv run python -m src.laser_ci_lg.cli clean vendorname
uv run python -m src.laser_ci_lg.cli run --scraper vendorname
```

For full scraper development guide, see `src/laser_ci_lg/scrapers/README.md`

## Canonical Spec Schema

Core fields normalized across all vendors:
- Optical: wavelength_nm, output_power_mw, linewidth, beam quality (M²)
- Stability: rms_noise_pct, power_stability_pct
- Modulation: analog/digital frequency limits, TTL shutter
- Fiber: output availability, NA, mode field diameter
- Physical: dimensions, interfaces, warmup time
- Unmapped specs stored in `vendor_fields` JSON

## Monthly Reporting

Reports include:
- New products detected since last run
- Spec changes (power increases, new wavelengths, etc.)
- Benchmark tables comparing similar products (e.g., 488nm @ 100mW class)
- Stored in `reports/` directory with timestamp