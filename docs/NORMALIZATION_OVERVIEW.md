# Normalization System Overview

## Introduction

The normalization system in Laser CI transforms heterogeneous vendor specifications into a standardized canonical schema. This document explains the enhanced normalization pipeline with individual model extraction, batch processing, and improved LLM integration.

## Complete Pipeline Flow

```
1. DISCOVER → 2. EXTRACT → 3. NORMALIZE → 4. ANALYZE → 5. REPORT
```

### 1. DISCOVER (scrapers/ddgs_production.py)
- **Search-based discovery** using DuckDuckGo API
- Find product pages with queries like `site:coherent.com "OBIS" laser`
- Identify PDF datasheets automatically
- Efficient product discovery via search API

### 2. EXTRACT (extraction.py)
- Parse HTML tables with Pandas
- Extract PDF specs with Docling (ACCURATE mode)
- **Clean spec names** removing footnotes and units
- Handle vendor-specific edge cases

### 3. NORMALIZE (normalize_batch.py)
- **Extract individual models** from product families
- Map vendor fields to canonical schema
- **Parallel LLM processing** for efficiency
- Improved field coverage with heuristics + LLM fallback

### 4. ANALYZE (benchmark.py)
- Group products by wavelength/power class
- Compare specifications across vendors
- Identify competitive advantages

### 5. REPORT (reporter.py)
- Generate markdown reports
- Create comparison matrices
- Provide strategic insights

## Enhanced Model Extraction

### Problem: Product Families vs Individual Models

Previously, the system treated entire product families as single items:
```python
# Old approach - one entry for all OBIS models
{
    "name": "OBIS LX/LS Family",
    "wavelength_nm": "various",  # Not useful!
    "power": "various"
}
```

### Solution: Individual SKU Extraction

The new system extracts individual models from families:

```python
def extract_models_from_specs(raw_specs: dict) -> List[dict]:
    """Extract individual laser models from concatenated specs."""
    models = []
    
    # Pattern for OBIS models
    pattern = r'OBIS\s+(\w+)\s+(\d+)\s*nm.*?(\d+)\s*mW'
    
    for text in raw_specs.values():
        for match in re.finditer(pattern, str(text)):
            model_name, wavelength, power = match.groups()
            models.append({
                'name': f'OBIS {model_name} {wavelength}nm',
                'wavelength_nm': float(wavelength),
                'output_power_mw_nominal': float(power)
            })
    
    return models
```

**Result**: Extracts individual models instead of treating entire families as single items

## Improved Spec Name Cleaning

### Problem: Malformed Keys with Footnotes

Raw extraction produced keys like:
```python
"Wavelength (nm) 1 2 3" → Multiple footnotes
"Output Power (mW) †"   → Special characters
"M² < 1.2 4"           → Mixed units and footnotes
```

### Solution: Clean Spec Names

```python
def _clean_spec_name(self, spec_name: str) -> str:
    """Clean spec names for better normalization."""
    import re
    
    # Remove footnote numbers anywhere
    cleaned = re.sub(r'\s+\d+\s*', ' ', spec_name)
    
    # Remove units in parentheses
    cleaned = re.sub(r'\s*\([^)]+\)', '', cleaned)
    
    # Remove special characters
    cleaned = re.sub(r'[†‡§¶]', '', cleaned)
    
    # Normalize whitespace
    cleaned = ' '.join(cleaned.split())
    
    return cleaned
```

**Result**: Clean keys that map correctly to canonical schema

## Batch Normalization with Parallel Processing

### Traditional Sequential Processing
```python
# Old: Process one model at a time
for model in models:
    normalized = normalize_single(model)  # Slow!
    save(normalized)
```

### New Parallel Batch Processing
```python
def normalize_all_batch(use_llm=True, max_workers=5):
    """Batch normalization with parallel LLM calls."""
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all models for parallel processing
        futures = []
        for model_specs in all_models:
            future = executor.submit(normalize_model, model_specs)
            futures.append(future)
        
        # Collect results as they complete
        for future in as_completed(futures):
            result = future.result()
            save_normalized(result)
```

**Benefit**: Parallel processing improves throughput

## LLM Enhancement Strategy

### Intelligent LLM Usage

The system only calls OpenAI when necessary:

```python
def needs_llm_enhancement(canonical_specs: dict) -> bool:
    """Determine if LLM help is needed."""
    
    # Count populated fields
    populated = sum(1 for v in canonical_specs.values() if v is not None)
    
    # Need LLM if < 4 critical fields mapped
    critical_fields = ['wavelength_nm', 'output_power_mw_nominal', 
                      'rms_noise_pct', 'beam_diameter_mm']
    
    critical_populated = sum(1 for f in critical_fields 
                           if canonical_specs.get(f) is not None)
    
    return critical_populated < 4
```

### Structured LLM Output

Using OpenAI's JSON schema for guaranteed valid output:

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": EXTRACTION_PROMPT},
        {"role": "user", "content": f"Extract specs from: {raw_specs}"}
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "laser_specs",
            "schema": {
                "type": "object",
                "properties": {
                    "wavelength_nm": {"type": ["number", "null"]},
                    "output_power_mw_nominal": {"type": ["number", "null"]},
                    # ... other fields
                }
            }
        }
    }
)
```

## Real-World Examples

### Example 1: Coherent OBIS Family

**Raw PDF content** (concatenated table):
```
OBIS LX 375 375nm 16mW OBIS LX 405 405nm 50mW OBIS LX 445 445nm 75mW...
```

**After extraction and cleaning**:
```python
models = [
    {"name": "OBIS LX 375", "Wavelength": "375", "Output Power": "16"},
    {"name": "OBIS LX 405", "Wavelength": "405", "Output Power": "50"},
    {"name": "OBIS LX 445", "Wavelength": "445", "Output Power": "75"}
]
```

**After normalization**:
```python
normalized = [
    {
        "product_name": "OBIS LX 375",
        "wavelength_nm": 375.0,
        "output_power_mw_nominal": 16.0,
        "manufacturer": "Coherent"
    },
    {
        "product_name": "OBIS LX 405", 
        "wavelength_nm": 405.0,
        "output_power_mw_nominal": 50.0,
        "manufacturer": "Coherent"
    }
]
```

### Example 2: Hübner Photonics Cobolt

**Raw specs with footnotes**:
```json
{
    "Wavelength 1 2": "561 nm",
    "Output power 3 4": "100 mW",
    "RMS noise (20 Hz - 20 MHz) 5": "< 0.3 %"
}
```

**After cleaning**:
```json
{
    "Wavelength": "561 nm",
    "Output power": "100 mW", 
    "RMS noise": "< 0.3 %"
}
```

**After normalization**:
```python
{
    "wavelength_nm": 561.0,
    "output_power_mw_nominal": 100.0,
    "rms_noise_pct": 0.3
}
```

### Example 3: LLM Enhancement for Unusual Fields

**Vendor-specific naming**:
```json
{
    "λ": "532nm",
    "P_out": "200mW",
    "Noise (rms)": "0.1%",
    "TEM_00": ">99%"
}
```

**Heuristics fail** (only 1 field mapped):
```python
{
    "wavelength_nm": None,  # "λ" not recognized
    "output_power_mw_nominal": None,  # "P_out" not recognized
    "rms_noise_pct": 0.1,  # Pattern matched
    "tem00_pct": None  # "TEM_00" not recognized
}
```

**LLM correctly interprets**:
```python
{
    "wavelength_nm": 532.0,  # λ = wavelength
    "output_power_mw_nominal": 200.0,  # P_out = power output
    "rms_noise_pct": 0.1,
    "tem00_pct": 99.0  # TEM00 mode purity
}
```

## Metrics to Track

Once in production, we plan to measure:

### Extraction Metrics
- Percentage of clean spec keys extracted
- Number of individual models vs product families
- Processing time per PDF
- Success rate by vendor

### Normalization Metrics  
- Fields mapped by heuristics alone
- Fields requiring LLM enhancement
- Coverage percentage per vendor
- Processing time comparison (sequential vs parallel)

## Key Functions Reference

### normalize_batch.py
```python
def normalize_all_batch(use_llm=True, max_workers=5):
    """Main entry point for batch normalization."""

def process_product_batch(products: List[Product], use_llm: bool):
    """Process a batch of products in parallel."""

def normalize_model_specs(model_data: dict, use_llm: bool):
    """Normalize specs for a single model."""
```

### extraction.py
```python
def _clean_spec_name(spec_name: str) -> str:
    """Remove footnotes and units from spec names."""

def extract_individual_models(raw_specs: dict) -> List[dict]:
    """Extract individual SKUs from product families."""
```

### llm.py
```python
def llm_normalize_batch(models: List[dict], model="gpt-4o-mini"):
    """Batch LLM normalization with structured output."""
```

## Configuration

### Target Products (config/target_products.yml)
```yaml
vendors:
  - name: Coherent
    max_products: 100
    segments:
      - id: diode_instrumentation
        product_patterns:
          - "OBIS"
          - "OBIS LX"
          - "OBIS LS"
          # ... 15 more patterns
```

### Environment Variables
```bash
OPENAI_API_KEY=sk-...        # Required for LLM
OPENAI_MODEL=gpt-4o-mini    # Optional model override
MAX_WORKERS=5                # Parallel processing threads
```

## Troubleshooting

### Low Normalization Rate
1. Check if spec names need cleaning
2. Add patterns to canonical_key() mapping
3. Verify LLM is enabled with --use-llm

### Duplicate Models
1. Check extraction patterns for overlaps
2. Verify model name uniqueness
3. Review database constraints

### LLM Timeouts
1. Reduce batch size (max_workers)
2. Use faster model (gpt-4o-mini)
3. Check OpenAI API status

## Summary

The enhanced normalization system provides:
- Individual model extraction from product families
- Clean spec extraction with footnote removal
- Parallel batch processing for efficiency
- LLM fallback for improved normalization coverage
- Structured output guarantees from OpenAI

This enables accurate competitive analysis with complete, normalized specifications for every laser model tracked in the system.