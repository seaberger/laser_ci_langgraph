# Coherent.com Laser Spec Scraping Analysis

## Products Being Scraped

### Diode/Instrumentation Lasers
1. **OBIS LX/LS**
   - Product URL: https://www.coherent.com/lasers/cw-solid-state/obis-ls-lx
   - Datasheet PDF: https://www.coherent.com/resources/datasheet/lasers/obis-family-ds.pdf

### Light Engines
1. **OBIS CellX**
   - Product URL: https://www.coherent.com/lasers/laser-engine/cellx
   - Datasheet PDF: https://www.coherent.com/resources/datasheet/lasers/cellx-ds.pdf

2. **OBIS Galaxy**
   - Product URL: https://www.coherent.com/lasers/laser-engine/galaxy
   - Datasheet PDF: https://www.coherent.com/resources/datasheet/lasers/obis-galaxy-integrated-system-ds.pdf

## Current Extraction Method

The Coherent scraper uses a **basic extraction approach**:

1. **HTML Pages**: Extracts all `<li>` bullet points that contain a colon (:)
   - Splits on first colon to create key-value pairs
   - Example: `"Wavelength: 488 nm"` → `{"Wavelength": "488 nm"}`

2. **PDF Files**: Extracts full text using pdfplumber but doesn't parse specs

## Specs That Will Be Captured

Based on the current implementation and canonical mapping, the following specs will be extracted if they appear as bullet points with colons:

### Optical Specifications
- **Wavelength** (nm) - Maps to `wavelength_nm`
  - Matches: "Wavelength", "λ", "Lambda", "Emission wavelength"
- **Output Power** (mW) - Maps to `output_power_mw_nominal`
  - Matches: "Output power", "Optical power", "CW power", "Typ. power"
- **Minimum Power** (mW) - Maps to `output_power_mw_min`
  - Matches: "Min. power", "Power min"
- **Linewidth** (MHz/nm) - Maps to `linewidth_mhz` or `linewidth_nm`
  - Matches: "Linewidth", "Spectral linewidth", "FWHM"

### Beam Quality
- **M²** - Maps to `m2`
  - Matches: "M2", "M^2", "Beam quality"
- **Beam Diameter** (mm) - Maps to `beam_diameter_mm`
  - Matches: "Beam diameter", "Output beam diameter"
- **Beam Divergence** (mrad) - Maps to `beam_divergence_mrad`
  - Matches: "Beam divergence", "Half-angle divergence"
- **Polarization** - Maps to `polarization`
  - Matches: "Polarization"

### Stability & Noise
- **RMS Noise** (%) - Maps to `rms_noise_pct`
  - Matches: "RMS noise", "Noise", "Intensity noise"
- **Power Stability** (%) - Maps to `power_stability_pct`
  - Matches: "Power stability", "Long-term stability", "LTP"

### Modulation & Control
- **Analog Modulation** (Hz) - Maps to `modulation_analog_hz`
  - Matches: "Analog modulation", "AM bandwidth"
- **Digital Modulation** (Hz) - Maps to `modulation_digital_hz`
  - Matches: "Digital modulation", "TTL modulation", "Blanking rate"
- **TTL Shutter** - Maps to `ttl_shutter`
  - Matches: "Electronic shutter", "Laser inhibit"

### Fiber Output
- **Fiber Output** (boolean) - Maps to `fiber_output`
  - Matches: "Fiber output", "Fiber delivery"
- **Fiber NA** - Maps to `fiber_na`
  - Matches: "Fiber NA", "NA"
- **Mode Field Diameter** (µm) - Maps to `fiber_mfd_um`
  - Matches: "Mode field diameter", "MFD"

### Physical & Interface
- **Dimensions** (mm) - Maps to `dimensions_mm`
  - Matches: "Dimensions", "Size", "Footprint"
- **Interfaces** - Maps to `interfaces`
  - Matches: "Interface", "Interfaces", "Control interface"
- **Warm-up Time** (min) - Maps to `warmup_time_min`
  - Matches: "Warm-up time", "Warmup time"

## Limitations & Issues

### Current Limitations:
1. **HTML Parsing**: Only captures specs in `<li>` tags with colons
   - May miss specs in tables, divs, or other formats
   - Won't capture multi-line specifications

2. **PDF Parsing**: Extracts text but doesn't parse it for specs
   - Raw text is saved but not processed into key-value pairs
   - Relies on LLM fallback for PDF spec extraction

3. **No Table Extraction**: Unlike base scraper's `extract_table_kv_pairs()`, Coherent scraper doesn't use it

### Potential Missed Specs:
- Specs in HTML tables (common on product pages)
- Specs without colons (e.g., "488 nm wavelength")
- Complex specs spanning multiple lines
- Specs in PDF tables or structured sections

## Recommendations for Improvement

1. **Add Table Extraction**: Use the base scraper's `extract_table_kv_pairs()` method
2. **Enhanced PDF Parsing**: Parse PDF tables and structured sections
3. **Broader HTML Parsing**: Look for specs in divs, spans, and definition lists
4. **Pattern Matching**: Add regex patterns for common Coherent spec formats
5. **Fallback to Full Text**: If no structured specs found, parse full text for known patterns

## Data Flow

1. **Scraping**: Coherent URLs → HTML/PDF content → Raw specs (if HTML with `<li>:` format)
2. **Normalization**: Raw specs → Heuristic mapping → Canonical schema
3. **LLM Fallback**: If <4 specs mapped → OpenAI processes raw text → Fill missing specs
4. **Storage**: Normalized specs → SQLite database with timestamps