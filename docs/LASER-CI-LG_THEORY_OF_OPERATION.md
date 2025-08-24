# LASER-CI-LG Theory of Operation

## Executive Summary

LASER-CI-LG (Laser Competitive Intelligence - LangGraph) is an automated competitive intelligence pipeline that monitors laser manufacturer specifications, normalizes heterogeneous data into a canonical schema, and generates strategic analysis reports. Built on LangGraph's state machine architecture with OpenAI integration, the system provides Coherent with real-time competitive insights across the laser instrumentation market.

## Architecture Overview

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         LangGraph Pipeline                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐   ┌───────┐   ┌───────────┐   ┌──────┐   ┌─────┐ │
│  │Bootstrap │→→→│ Crawl │→→→│ Normalize │→→→│Report│→→→│Bench│ │
│  └──────────┘   └───────┘   └───────────┘   └──────┘   └─────┘ │
│       ↓             ↓             ↓              ↓         ↓     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    SQLite Database                        │   │
│  │  ┌────────────┐  ┌──────────┐  ┌──────────────────┐    │   │
│  │  │Manufacturer│  │ Products │  │  Raw Documents   │    │   │
│  │  └────────────┘  └──────────┘  └──────────────────┘    │   │
│  │                        ↓                                 │   │
│  │                ┌──────────────────┐                     │   │
│  │                │Normalized Specs  │                     │   │
│  │                └──────────────────┘                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  External Services:                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ Vendor Sites│  │ OpenAI API   │  │ Playwright Browser│      │
│  └─────────────┘  └──────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

## LangGraph Integration

### Why LangGraph?

LangGraph provides several critical capabilities for this pipeline:

1. **State Management**: Maintains pipeline state across nodes, tracking progress and data
2. **Directed Graph Flow**: Ensures operations execute in correct sequence
3. **Error Recovery**: Built-in retry and error handling mechanisms
4. **Checkpointing**: Can resume from failure points
5. **Observability**: Clear visibility into pipeline execution

### State Machine Definition

```python
# From graph.py
def graph_builder() -> StateGraph:
    workflow = StateGraph(State)
    
    # Define nodes (each is a processing stage)
    workflow.add_node("bootstrap", bootstrap)
    workflow.add_node("crawl", crawl)
    workflow.add_node("normalize", normalize)
    workflow.add_node("report", report)
    workflow.add_node("bench", bench)
    
    # Define edges (execution flow)
    workflow.add_edge(START, "bootstrap")
    workflow.add_edge("bootstrap", "crawl")
    workflow.add_edge("crawl", "normalize")
    workflow.add_edge("normalize", "report")
    workflow.add_edge("report", "bench")
    workflow.add_edge("bench", END)
    
    return workflow.compile()
```

### State Object

The pipeline maintains state throughout execution:

```python
class State(TypedDict):
    bootstrap_complete: bool
    crawl_stats: dict
    normalized_count: int
    report_path: str
    benchmark_results: dict
    use_llm: bool
    llm_model: str
    force_refresh: bool
```

## Pipeline Nodes in Detail

### 1. Bootstrap Node

**Purpose**: Initialize database and load configuration

**Operations**:
- Creates SQLite database schema if not exists
- Loads manufacturer and product data from `config/competitors.yml`
- Seeds database with vendor/product relationships
- Validates configuration integrity

**Example Configuration Entry**:
```yaml
- name: Coherent
  homepage: "https://www.coherent.com"
  segments:
    - id: diode_instrumentation
      products:
        - name: "OBIS LX/LS Lasers"
          product_url: "https://www.coherent.com/lasers/obis"
          datasheets:
            - "https://www.coherent.com/resources/obis-family-ds.pdf"
```

### 2. Crawl Node

**Purpose**: Fetch and extract specifications from vendor websites

**Intelligent Scraping System**:

#### Auto-Detection Logic

The system automatically determines the optimal fetching strategy:

```python
def requires_browser(self, url: str, initial_response=None) -> bool:
    """Detects if browser automation is needed"""
    
    # Check 1: PDF URLs returning HTML (dynamic generation)
    if url.lower().endswith('.pdf'):
        if 'html' in initial_response.headers.get('content-type', ''):
            return True
    
    # Check 2: Single Page Application markers
    spa_markers = ['__NUXT__', '__NEXT_DATA__', 'React.', 'Vue.']
    if any(marker in initial_response.text for marker in spa_markers):
        return True
    
    # Check 3: Minimal HTML with JavaScript dependency
    if len(initial_response.text) < 5000 and '<script' in initial_response.text:
        return True
    
    return False
```

#### Fetching Strategies

1. **Standard HTTP** (requests library):
   - Static HTML pages
   - Direct PDF downloads
   - Simple server-rendered content

2. **Headless Browser** (Playwright):
   - JavaScript-rendered SPAs
   - Dynamic PDF generation
   - Pages requiring interaction

**Example: Lumencor Detection**:
```python
# Initial request returns minimal HTML with Nuxt.js
response = requests.get("https://lumencor.com/products/celesta")
# Detects: window.__NUXT__ in response → triggers browser mode

# Browser automation handles dynamic content
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    # Waits for JavaScript to render content
    content = page.content()  # Fully rendered HTML
```

### 3. Normalize Node

**Purpose**: Transform vendor-specific specs to canonical schema

**Process**: See [NORMALIZATION_OVERVIEW.md](./NORMALIZATION_OVERVIEW.md) for details

**Key Operations**:
- Merges specs from multiple documents per product
- Maps vendor fields to canonical schema via heuristics
- Falls back to LLM when < 4 fields mapped
- Stores normalized data for analysis

### 4. Report Node

**Purpose**: Generate competitive intelligence reports

**Report Types**:
1. **Technical Comparison**: Side-by-side spec comparisons
2. **Market Positioning**: Segment analysis and coverage
3. **Feature Matrix**: Capability comparison grid
4. **AI Analysis**: GPT-4o strategic insights

### 5. Bench Node

**Purpose**: Benchmark competitors against Coherent products

**Operations**:
- Identifies comparable products by wavelength/power class
- Calculates performance deltas
- Highlights competitive advantages
- Generates win/loss analysis

## Extraction System

### HTML Extraction

The system uses multiple strategies to extract specifications from HTML:

#### 1. Pandas Table Parsing
```python
tables = pd.read_html(html_text)
for table in tables:
    # Convert table to key-value pairs
    if len(table.columns) == 2:
        for _, row in table.iterrows():
            specs[str(row[0])] = str(row[1])
```

#### 2. BeautifulSoup Pattern Matching
```python
soup = BeautifulSoup(html_text, 'html.parser')

# Find specification patterns
for tag in soup.find_all(['td', 'th', 'div', 'span']):
    text = tag.get_text()
    # Match patterns like "Wavelength: 488 nm"
    if ':' in text:
        key, value = text.split(':', 1)
        specs[key.strip()] = value.strip()
```

#### 3. Vendor-Specific Fixes

**Omicron Concatenated Table Issue**:
```python
# Problem: Entire product table as single string
# "LuxX+ 488 488 nm / 100 mW LuxX+ 515 515 nm / 50 mW..."

# Solution: Regex extraction
pattern = r'(LuxX\+?\s*\d+)\s+(\d+)\s*nm\s*/\s*(\d+)\s*mW'
for match in re.finditer(pattern, text):
    model, wavelength, power = match.groups()
    specs[model] = {
        'Wavelength': f'{wavelength} nm',
        'Output Power': f'{power} mW'
    }
```

### PDF Extraction with Docling

Docling provides advanced PDF table extraction:

```python
from docling.document_converter import DocumentConverter
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

def extract_pdf_specs_with_docling(pdf_content):
    # Configure for ACCURATE mode (best quality)
    pipeline = StandardPdfPipeline(
        backend=PyPdfiumDocumentBackend,
        table_structure_options={
            "mode": "accurate",  # High-quality table detection
            "detect_borderless": True
        }
    )
    
    converter = DocumentConverter(pipeline=pipeline)
    result = converter.convert(pdf_content)
    
    # Extract tables as markdown
    markdown = result.document.export_to_markdown()
    # Parse markdown tables for specs
```

**Oxxius Column Alignment Fix**:
```python
# Problem: PDF columns misaligned
# | Wavelength | Output Power | → | 375 | nm | 50 | mW |

# Solution: Track column positions
def _parse_markdown_table(markdown):
    headers = ['Wavelength', 'Output Power', ...]
    for row in table_rows:
        cells = row.split('|')
        # Correctly map based on position, not sequence
        specs['Wavelength'] = f'{cells[1]} {cells[2]}'  # "375 nm"
        specs['Output Power'] = f'{cells[3]} {cells[4]}'  # "50 mW"
```

## Scraper System Architecture

### Base Scraper Pattern

All scrapers inherit from `BaseScraper`:

```python
class BaseScraper:
    def iter_targets(self):
        """Yields URLs from config"""
        
    def fetch_with_cache(self, url):
        """Smart fetching with caching"""
        if self.requires_browser(url):
            return self.fetch_with_browser(url)
        else:
            return self.fetch_standard(url)
    
    def store_document(self, session, target, ...):
        """Database storage with deduplication"""
```

### Content Fingerprinting

Prevents reprocessing unchanged content:

```python
def calculate_content_hash(content: bytes) -> str:
    """SHA-256 hash for content fingerprinting"""
    return hashlib.sha256(content).hexdigest()

# Skip if hash unchanged
existing = session.query(RawDocument).filter_by(
    url=url, 
    content_hash=new_hash
).first()
if existing:
    return  # Skip reprocessing
```

### PDF Caching

PDFs are cached locally for efficiency:

```
data/pdf_cache/
├── coherent/
│   ├── obis-family-ds.pdf
│   └── cellx-ds.pdf
├── omicron/
│   └── luxx_plus_datasheet201901.pdf
└── oxxius/
    └── Oxxius-Datasheet-2022.pdf
```

## Adding New Competitors

### Step 1: Configure in competitors.yml

```yaml
- name: NewVendor
  homepage: "https://newvendor.com"
  segments:
    - id: diode_instrumentation
      products:
        - name: "Model XYZ"
          product_url: "https://newvendor.com/xyz"
          datasheets:
            - "https://newvendor.com/xyz.pdf"
```

### Step 2: Create Scraper

```python
# src/laser_ci_lg/scrapers/newvendor.py
from .base import BaseScraper
from ..db import SessionLocal

class NewVendorScraper(BaseScraper):
    def vendor(self) -> str:
        return "NewVendor"
    
    def run(self):
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                # Automatic detection handles browser vs standard
                status, content_type, text, content_hash, file_path, raw_specs = \
                    self.fetch_with_cache(tgt["url"])
                
                self.store_document(s, tgt, status, content_type, text,
                                  content_hash, file_path, raw_specs)
            s.commit()
        finally:
            s.close()
```

### Step 3: Register in Crawler

```python
# crawler.py
from .scrapers.newvendor import NewVendorScraper

# In build_scrapers():
elif v["name"] == "NewVendor":
    scrapers.append(NewVendorScraper(t, force_refresh=force_refresh))
```

## OpenAI Integration

### Normalization Enhancement

When heuristics map < 4 fields, LLM assists:

```python
def llm_normalize(raw_specs: dict, text_blob: str):
    client = OpenAI()
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract laser specifications..."},
            {"role": "user", "content": f"Specs: {raw_specs}\nText: {text_blob}"}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "laser_specs",
                "schema": CANONICAL_SCHEMA
            }
        }
    )
    
    return json.loads(response.choices[0].message.content)
```

### Competitive Analysis

AI-powered strategic insights:

```python
def generate_ai_analysis(competitive_data):
    client = OpenAI()
    
    response = client.chat.completions.create(
        model="gpt-4o",  # or o3-pro for reasoning
        messages=[
            {"role": "system", "content": ANALYSIS_PROMPT},
            {"role": "user", "content": json.dumps(competitive_data)}
        ]
    )
    
    return response.choices[0].message.content
```

## Performance Optimizations

### Parallel Scraping
- Multiple scrapers run concurrently
- Thread pool for network I/O
- Async browser contexts for Playwright

### Incremental Processing
- Content hashing prevents reprocessing
- Only new/changed documents normalized
- Cached PDFs reused across runs

### Smart LLM Usage
- Heuristics first (free and fast)
- LLM only when needed (< 4 fields)
- Model selection based on complexity

## Database Schema

### Core Tables

```sql
-- Vendors
CREATE TABLE manufacturers (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    homepage TEXT
);

-- Products
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    manufacturer_id INTEGER REFERENCES manufacturers(id),
    segment_id TEXT,
    name TEXT NOT NULL,
    product_url TEXT
);

-- Raw scraped data
CREATE TABLE raw_documents (
    id INTEGER PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    url TEXT NOT NULL,
    content_type TEXT,  -- 'html' or 'pdf_text'
    text TEXT,
    raw_specs JSON,     -- Extracted key-value pairs
    content_hash TEXT,  -- SHA-256 for deduplication
    file_path TEXT,     -- Local PDF cache path
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Normalized specifications
CREATE TABLE normalized_specs (
    id INTEGER PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    wavelength_nm REAL,
    output_power_mw_nominal REAL,
    rms_noise_pct REAL,
    -- ... other canonical fields ...
    vendor_fields JSON,  -- Unmapped specs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Example: Complete Flow for One Product

### 1. Bootstrap
```
Config: Omicron LuxX+ 488
URL: https://omicron-laserage.com/luxx
PDF: https://omicron-laserage.com/luxx_datasheet.pdf
→ Database: Product ID 42 created
```

### 2. Crawl
```
Fetch: https://omicron-laserage.com/luxx
Detect: Static HTML → Use requests
Extract: 15 specs from HTML tables
Store: raw_documents with raw_specs JSON
```

### 3. Normalize
```
Input: {"Wavelength": "488 nm", "Output Power": "100 mW", ...}
Heuristic: 12/15 fields mapped
Result: normalized_specs entry created
```

### 4. Report
```
Compare: LuxX+ 488 vs Coherent OBIS 488
Advantage: Coherent +20% power, -50% noise
Output: reports/2025-08-24_competitive_analysis.md
```

### 5. Bench
```
Benchmark: 488nm @ 100mW class
Coherent: 120mW, 0.1% RMS
Omicron: 100mW, 0.2% RMS
Result: Coherent superior in this class
```

## Monitoring and Maintenance

### Health Checks
- Verify scraper success rates
- Monitor extraction quality (specs per product)
- Track LLM usage and costs
- Alert on vendor site changes

### Regular Updates
- Add new products as released
- Update scraper logic for site changes
- Refine extraction patterns
- Expand canonical schema as needed

## Summary

LASER-CI-LG leverages LangGraph's state machine architecture to create a robust, automated competitive intelligence pipeline. The system's intelligent scraping, advanced extraction, and AI-powered analysis provide Coherent with comprehensive market insights. Key innovations include automatic browser detection, vendor-specific extraction fixes, and seamless LLM integration for data normalization and strategic analysis.

For detailed component documentation, see:
- [NORMALIZATION_OVERVIEW.md](./NORMALIZATION_OVERVIEW.md) - Normalization system details
- [Scraper README](../src/laser_ci_lg/scrapers/README.md) - Scraper development guide
- [EXTRACTION_FINAL_RESULTS.md](./EXTRACTION_FINAL_RESULTS.md) - Extraction system results