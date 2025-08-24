# Normalization System Overview

## Introduction

The normalization system in Laser CI transforms heterogeneous vendor specifications into a standardized canonical schema. This document explains how `normalize.py` works and how it fits into the complete data pipeline.

## Complete Pipeline Flow

```
1. SCRAPE → 2. PARSE → 3. DATABASE → 4. NORMALIZE → 5. REPORT
```

### 1. SCRAPE (scrapers/*.py)
- Fetch HTML pages and PDF datasheets from vendor websites
- Handle caching and duplicate detection via content hashing
- Support for dynamic content via Playwright browser automation

### 2. PARSE (extraction.py)
- Extract key-value pairs from HTML tables and PDF documents
- Handle vendor-specific quirks (concatenated tables, column misalignment)
- Store raw specifications as JSON in database

### 3. DATABASE (models.py, db.py)
- Store raw documents with extracted specs
- Track content changes via SHA-256 hashing
- Maintain relationships: Manufacturer → Product → RawDocument

### 4. NORMALIZE (normalize.py)
- Convert vendor-specific field names to canonical schema
- Parse values with units to numeric representations
- Use LLM fallback when heuristics fail
- **Runs automatically** after crawl phase completes
- No manual intervention required

### 5. REPORT (reporter.py, enhanced_reporter.py)
- Generate competitive intelligence reports
- Compare normalized specs across vendors
- Identify market positioning and technical advantages

## When Normalization Occurs

The normalize function is **automatically executed** as part of the LangGraph pipeline workflow and does NOT need to be manually started.

### Automatic Pipeline Integration

The normalization step is wired into the LangGraph state machine (graph.py):

```python
# Linear workflow definition
workflow.add_edge("crawl", "normalize")      # Runs after crawl
workflow.add_edge("normalize", "report")     # Runs before report
```

### Execution Triggers

1. **Every `cli run` command** - Normalization always executes as part of the pipeline
2. **After all scrapers complete** - Waits for crawl phase to finish
3. **Before report generation** - Must complete for reports to have data
4. **Incremental processing** - Only processes new/changed documents

### Example Pipeline Execution

```bash
$ uv run python -m src.laser_ci_lg.cli run

→ Starting bootstrap...
  ✓ Database initialized
  
→ Starting crawl...
  ✓ Fetched 35 documents
  
→ Starting normalize...  # AUTOMATIC - no user action needed
  ✓ Processed 35 products
  ✓ Heuristics mapped 28 products
  ✓ LLM enhanced 7 products
  
→ Starting report...
  ✓ Report generated
```

## How normalize.py Works

### Core Functions

#### 1. `normalize_all(use_llm=True, model=None)`
Main entry point that processes all raw documents and creates normalized specifications.

```python
def normalize_all(use_llm: bool = True, model: str | None = None) -> int:
    """Return count of inserted NormalizedSpec rows."""
```

**Process:**
1. Fetch all raw documents from database
2. Group documents by product_id
3. Merge raw specs from multiple documents per product
4. Apply normalization logic
5. Store results in NormalizedSpec table

#### 2. `simple_kv_from_text(text: str)`
Fallback extraction for documents without structured specs.

```python
def simple_kv_from_text(text: str) -> dict:
    kv = {}
    for line in text.splitlines():
        if ":" in line and len(line) < 120:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    return kv
```

### Normalization Process

The normalization happens in three stages:

#### Stage 1: Merge Raw Specs
```python
for pid, docs in by_pid.items():
    merged_raw, blobs = {}, []
    for d in docs:
        if d.raw_specs:
            merged_raw.update(d.raw_specs)
        blobs.append(d.text)
```

#### Stage 2: Heuristic Mapping
```python
canonical = {k: None for k in CANONICAL_SPEC_KEYS}
extras = {}
for k, v in merged_raw.items():
    ck = canonical_key(k)  # Maps vendor field to canonical
    if ck:
        canonical[ck] = parse_value_to_unit(ck, str(v))
    else:
        extras[k] = v  # Store unmapped fields
canonical["vendor_fields"] = extras or None
```

#### Stage 3: LLM Fallback
```python
if use_llm and sum(v is not None for v in canonical.values()) < 4:
    llm = llm_normalize(merged_raw, "\n".join(blobs[:2]), model=model)
    for k in CANONICAL_SPEC_KEYS:
        if llm.get(k) is not None:
            canonical[k] = llm.get(k)
```

## Examples

### Example 1: Coherent OBIS Laser

**Raw specs from extraction:**
```json
{
  "Wavelength": "488 nm",
  "Output Power": "60 mW",
  "RMS Noise": "< 0.2 %",
  "Power Stability": "< ±0.5 %",
  "Beam Diameter": "0.7 ± 0.05 mm",
  "M²": "< 1.2",
  "TTL Modulation": "Yes",
  "Analog Modulation": "0-10V"
}
```

**After heuristic normalization:**
```python
{
  "wavelength_nm": 488.0,
  "output_power_mw_nominal": 60.0,
  "rms_noise_pct": 0.2,
  "power_stability_pct": 0.5,
  "beam_diameter_mm": 0.7,
  "m2": 1.2,
  "ttl_shutter": True,
  "analog_modulation": "0-10V",
  "vendor_fields": {}
}
```

### Example 2: Omicron LuxX+ Laser

**Raw specs (concatenated table issue):**
```json
{
  "Product Table": "LuxX+ 488 488 nm / 100 mW LuxX+ 515 515 nm / 50 mW..."
}
```

**After extraction fix and normalization:**
```python
{
  "wavelength_nm": 488.0,
  "output_power_mw_nominal": 100.0,
  "vendor_fields": {
    "Product Model": "LuxX+ 488"
  }
}
```

### Example 3: Oxxius Laser (PDF with column misalignment)

**Raw specs (misaligned):**
```json
{
  "Wavelength": "375",
  "Output Power": "nm",
  "Linewidth": "50 mW"
}
```

**After PDF fix and normalization:**
```python
{
  "wavelength_nm": 375.0,
  "output_power_mw_nominal": 50.0,
  "vendor_fields": {}
}
```

### Example 4: LLM Fallback

**When heuristics yield < 4 fields:**

**Raw specs:**
```json
{
  "λ": "532nm",
  "P_out": "200mW",
  "Noise (rms)": "0.1%"
}
```

**Heuristic result (only 1 field mapped):**
```python
{
  "wavelength_nm": None,  # "λ" not recognized
  "output_power_mw_nominal": None,  # "P_out" not recognized
  "rms_noise_pct": 0.1,  # Recognized pattern
  ...
}
```

**LLM input:**
```json
{
  "raw_specs": {"λ": "532nm", "P_out": "200mW", "Noise (rms)": "0.1%"},
  "text_blob": "Product datasheet text..."
}
```

**LLM output (structured JSON):**
```python
{
  "wavelength_nm": 532.0,
  "output_power_mw_nominal": 200.0,
  "rms_noise_pct": 0.1,
  "vendor_fields": {}
}
```

## Canonical Schema

The canonical schema (`CANONICAL_SPEC_KEYS` in specs.py) includes:

### Optical Specifications
- `wavelength_nm`: Center wavelength in nanometers
- `output_power_mw_nominal`: Nominal output power in milliwatts
- `output_power_mw_min`: Minimum guaranteed power
- `output_power_mw_max`: Maximum power capability
- `linewidth_mhz`: Spectral linewidth in MHz
- `linewidth_nm`: Spectral linewidth in nm
- `m2`: Beam quality factor (M²)
- `beam_diameter_mm`: Beam diameter at aperture

### Stability Metrics
- `rms_noise_pct`: RMS noise as percentage
- `power_stability_pct`: Power stability over time
- `wavelength_stability_pm_c`: Wavelength stability per °C

### Modulation Capabilities
- `ttl_shutter`: TTL modulation available (boolean)
- `analog_modulation`: Analog modulation range
- `analog_freq_limit_khz`: Analog bandwidth in kHz
- `digital_freq_limit_khz`: Digital modulation bandwidth

### Physical Properties
- `warmup_minutes`: Warmup time to stable operation
- `coherence_length_m`: Coherence length in meters
- `polarization_ratio`: Polarization extinction ratio

### Fiber Output
- `fiber_output_available`: Fiber coupling option (boolean)
- `fiber_na`: Numerical aperture
- `fiber_core_diameter_um`: Core diameter in micrometers

## Key Utility Functions

### canonical_key() (from specs.py)
Maps vendor-specific field names to canonical schema:

```python
def canonical_key(vendor_key: str) -> str | None:
    """
    Examples:
    - "Wavelength" → "wavelength_nm"
    - "Output Power" → "output_power_mw_nominal"
    - "RMS Noise" → "rms_noise_pct"
    - "Beam Quality" → "m2"
    """
```

### parse_value_to_unit() (from specs.py)
Parses values with units to numeric representations:

```python
def parse_value_to_unit(canonical_key: str, value: str) -> float | str | bool | None:
    """
    Examples:
    - "488 nm" → 488.0
    - "< 0.2 %" → 0.2
    - "≤ 1.2" → 1.2
    - "Yes" → True
    - "10-45°C" → "10-45°C" (preserved as string)
    """
```

## LLM Integration (llm.py)

When heuristics fail (< 4 fields mapped), the system uses OpenAI's structured output:

```python
def llm_normalize(raw_specs: dict, text_blob: str, model: str = None) -> dict:
    """
    Uses OpenAI with json_schema response format to ensure valid output.
    
    Model selection:
    - Default: gpt-4o-mini (fast, cost-effective)
    - Optional: gpt-4o (more accurate)
    - Configurable via --model CLI flag or OPENAI_MODEL env var
    """
```

**Structured Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "wavelength_nm": {"type": ["number", "null"]},
    "output_power_mw_nominal": {"type": ["number", "null"]},
    "rms_noise_pct": {"type": ["number", "null"]},
    ...
  }
}
```

## Database Storage

Normalized specs are stored in the `normalized_specs` table:

```sql
CREATE TABLE normalized_specs (
    id INTEGER PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    source_raw_id INTEGER REFERENCES raw_documents(id),
    wavelength_nm REAL,
    output_power_mw_nominal REAL,
    output_power_mw_min REAL,
    output_power_mw_max REAL,
    rms_noise_pct REAL,
    power_stability_pct REAL,
    linewidth_mhz REAL,
    linewidth_nm REAL,
    m2 REAL,
    beam_diameter_mm REAL,
    ttl_shutter BOOLEAN,
    analog_modulation TEXT,
    vendor_fields JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Error Handling

The normalization system is designed to be resilient:

1. **Missing raw_specs**: Falls back to simple text extraction
2. **LLM failures**: Preserves heuristic results
3. **Invalid values**: Returns None for unparseable fields
4. **Duplicate products**: Uses latest document (ordered by fetched_at)

## Usage in CLI

```bash
# Run full pipeline including normalization
uv run python -m src.laser_ci_lg.cli run

# Run with specific LLM model
uv run python -m src.laser_ci_lg.cli run --model gpt-4o

# Skip LLM normalization (heuristics only)
uv run python -m src.laser_ci_lg.cli run --no-llm
```

## Performance Considerations

- **Batch Processing**: Groups documents by product to minimize database queries
- **LLM Optimization**: Only calls OpenAI when heuristics yield < 4 fields
- **Caching**: Uses content hashing to avoid re-processing unchanged documents
- **Model Selection**: Default gpt-4o-mini balances cost and quality

## Troubleshooting

### Common Issues

1. **Low field mapping rate**
   - Check vendor field names in raw_specs
   - Add mappings to canonical_key() function
   - Consider vendor-specific extraction logic

2. **LLM timeouts**
   - Reduce text_blob size (uses first 2 documents only)
   - Switch to faster model (gpt-4o-mini)
   - Increase timeout in OpenAI client

3. **Incorrect unit parsing**
   - Review parse_value_to_unit() patterns
   - Add vendor-specific unit formats
   - Preserve original values in vendor_fields

## Summary

The normalization system is the critical bridge between raw vendor data and standardized competitive intelligence. It combines deterministic heuristics with AI-powered fallbacks to achieve high extraction rates while maintaining data quality. The normalized data enables meaningful cross-vendor comparisons and powers the competitive analysis reports.