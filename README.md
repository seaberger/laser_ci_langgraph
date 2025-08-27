# Sightline Laser CI Module

A competitive intelligence module for the **Sightline** suite, built on **LangGraph** with **OpenAI** to provide ground truth data for knowledge engine, product finder, strategic marketing, and competitive analysis applications. The module:
- **Discover** laser products via search engine queries (DuckDuckGo API)
- **Extract** specifications from manufacturer sites (HTML/PDF) 
- **Normalize** heterogeneous specs into canonical schema (heuristics + LLM)
- **Track** changes with SHA-256 content fingerprinting
- **Benchmark** competitors vs **Coherent** models
- **Generate** strategic analysis reports monthly

## 🚀 Recent Major Updates

### Search-Based Discovery (v2.0)
- Replaced Playwright crawling with DuckDuckGo search API
- Smart filtering identifies product pages vs blog/news content
- Configurable per-vendor limits and rate limiting
- Successfully tested discovery across 5 vendors

### Enhanced Extraction & Normalization
- Individual SKU/model extraction from product families
- Clean spec names with footnote and unit removal
- Improved normalization using LLM fallback when needed
- Batch processing with parallel LLM calls for efficiency

### Unified Pipeline Architecture
- **Unified scrapers** supporting both search discovery and static URLs
- **SHA-256 content fingerprinting** prevents reprocessing
- **Target products configuration** with 98 specific laser models
- **Progress tracking** with resumable discovery on failure

## 📁 Project Structure

```
competitive-intel/
├── README.md
├── requirements.txt
├── config/
│   ├── target_products.yml      # 98 laser models to track
│   ├── competitors.yml          # Static URLs fallback
│   └── segments.yml             # Market segments
├── src/laser_ci_lg/
│   ├── cli.py                   # Command-line interface
│   ├── graph_unified.py         # LangGraph pipeline
│   ├── scrapers/
│   │   ├── ddgs_production.py   # DuckDuckGo discovery
│   │   ├── unified_base.py      # Base unified scraper
│   │   └── unified_*.py         # Vendor scrapers
│   ├── extraction.py            # HTML/PDF spec extraction
│   ├── normalize_batch.py       # Parallel normalization
│   └── llm.py                   # OpenAI integration
├── data/                        # Runtime data
│   ├── laser-ci.sqlite          # Database
│   └── pdf_cache/               # Cached PDFs
└── reports/                     # Generated reports
```

## 🔧 Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt

# Create .env file with your OpenAI API key
echo "OPENAI_API_KEY=sk-..." > .env
```

## 🎯 Quick Start

```bash
# Run complete pipeline (discover, extract, normalize, report)
uv run python -m src.laser_ci_lg.cli run

# Run specific vendor only
uv run python -m src.laser_ci_lg.cli run --scraper coherent

# Force refresh (bypass cache)
uv run python -m src.laser_ci_lg.cli run --force-refresh

# Schedule monthly runs
uv run python -m src.laser_ci_lg.cli schedule --cron "0 3 1 * *"
```

## 📊 Expected Performance Improvements

Based on our development testing, the search-based approach should provide:
- **Faster discovery** compared to full page crawling
- **More consistent results** without browser timeouts
- **Lower network usage** by fetching only search results
- **Better scalability** for adding more vendors

*Note: Actual metrics will be collected during production deployment.*

## 🔍 How It Works

### 1. Discovery Phase
Uses DuckDuckGo search API to find product pages:
```python
# Example search query
site:coherent.com "OBIS" laser product specification
```
- Identifies product pages vs marketing content
- Discovers PDF datasheets automatically
- Includes rate limiting between searches

### 2. Extraction Phase
Intelligently extracts specs from HTML and PDFs:
- **Pandas** for HTML table parsing
- **Docling** for PDF table extraction (ACCURATE mode)
- **Vendor-specific fixes** for edge cases
- **SHA-256 fingerprinting** prevents reprocessing

### 3. Normalization Phase
Transforms vendor specs to canonical schema:
- **Heuristic mapping** first (fast, free)
- **LLM enhancement** when <4 fields mapped
- **Batch processing** with parallel LLM calls
- **Individual model extraction** from product families

### 4. Analysis Phase
Generates competitive intelligence:
- **Technical comparisons** by wavelength/power class
- **Market positioning** analysis
- **Feature matrices** for capability comparison
- **Strategic insights** via GPT-4

## 🎯 Target Products Tracked

The system tracks **98 specific laser models** across 5 vendors:

### Coherent (19 patterns)
- OBIS variants (LX, LS, Core, LG, XT, Smart)
- Genesis series (standard, MX)
- Sapphire series (standard, LP)
- Verdi series (standard, G)
- Light engines (CellX, Galaxy, LaserBox, HIVE)

### Hübner Photonics/Cobolt (14 patterns)
- Cobolt series (04-01, 05-01, 06-01, 08-01)
- Individual models (Blues, Jive, Samba, Rumba, Mambo, etc.)

### Omicron (18 patterns)
- LuxX family with specific wavelengths
- BrixX, PhoxX, QuixX series

### Oxxius (28 patterns)
- LBX series (375-785nm)
- LCX combinable series
- LPX pulsed series
- SLIM ultra-low noise

### Lumencor (19 patterns)
- Light engines: CELESTA, ZIVA, SPECTRA, SOLA, AURA, RETRA, LIDA, PEKA

## 🏗️ Architecture Highlights

### LangGraph Pipeline
```python
Bootstrap → Discover/Crawl → Normalize → Report → Benchmark
```
- **State management** across pipeline nodes
- **Error recovery** with checkpointing
- **Observable** execution flow

### Content Deduplication
```python
# SHA-256 fingerprinting prevents reprocessing
content_hash = hashlib.sha256(content).hexdigest()
if document_exists_with_hash(url, content_hash):
    skip_processing()
```

### Intelligent Normalization
```python
# Canonical schema mapping
"Wavelength: 488 nm" → wavelength_nm: 488.0
"Output Power: 100 mW" → output_power_mw_nominal: 100.0
"RMS Noise: < 0.2%" → rms_noise_pct: 0.2
```

## 📈 Development Testing Results

During development testing, we successfully:
- Discovered products across all 5 configured vendors
- Extracted and normalized specifications
- Generated competitive analysis reports
- Avoided the timeout issues from browser-based crawling

### Vendors Successfully Tested
- Coherent (OBIS, Genesis series)
- Hübner Photonics (Cobolt series)
- Omicron (LuxX variants)
- Oxxius (LBX series)
- Lumencor (light engines)

## 🔮 Future Enhancements

- [ ] Add Thorlabs and Vortran Stradus scrapers
- [ ] Expand schema for driver I/O and warranty specs
- [ ] Implement Bing Search API for higher limits
- [ ] Add real-time alerting for spec changes
- [ ] Create web dashboard for results visualization

## 📚 Documentation

- [Theory of Operation](docs/LASER-CI-LG_THEORY_OF_OPERATION.md) - System architecture
- [Normalization Guide](docs/NORMALIZATION_OVERVIEW.md) - Spec normalization details
- [CLI Manual](docs/CLI_USER_MANUAL.md) - Command reference
- [Caching System](docs/CACHING_AND_FINGERPRINTING.md) - Content deduplication

## 🤝 Contributing

1. Add vendor config to `config/target_products.yml`
2. Create scraper in `src/laser_ci_lg/scrapers/`
3. Register in `crawler_unified.py`
4. Test with `uv run python -m src.laser_ci_lg.cli run --scraper vendor`

## 📝 License

Proprietary - Coherent Corp.