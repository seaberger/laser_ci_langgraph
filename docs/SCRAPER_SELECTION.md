# Scraper Selection Feature

## Overview
The scraper selection feature allows you to run specific scrapers individually instead of processing all vendors. This is useful for testing, debugging, or when you only need updates from specific manufacturers.

## CLI Usage

### Basic Syntax
```bash
uv run python -m src.laser_ci_lg.cli run --scraper <name>
```

### Available Scraper Names

| Primary Name | Aliases | Vendor |
|-------------|---------|--------|
| `coherent` | - | Coherent |
| `hubner` | `cobolt` | Hübner Photonics (Cobolt) |
| `omicron` | `luxx` | Omicron |
| `oxxius` | `lbx` | Oxxius |

### Examples

#### Run Single Scraper
```bash
# Run only Coherent scraper
uv run python -m src.laser_ci_lg.cli run --scraper coherent

# Run only Hübner/Cobolt (any of these work)
uv run python -m src.laser_ci_lg.cli run --scraper hubner
uv run python -m src.laser_ci_lg.cli run --scraper cobolt

# Run only Omicron
uv run python -m src.laser_ci_lg.cli run --scraper omicron
uv run python -m src.laser_ci_lg.cli run --scraper luxx

# Run only Oxxius
uv run python -m src.laser_ci_lg.cli run --scraper oxxius
uv run python -m src.laser_ci_lg.cli run --scraper lbx
```

#### Combine with Other Options
```bash
# Force refresh for specific scraper
uv run python -m src.laser_ci_lg.cli run --scraper coherent --force-refresh

# Use specific model for one vendor
uv run python -m src.laser_ci_lg.cli run --scraper omicron --model gpt-4o

# Disable LLM for specific scraper
uv run python -m src.laser_ci_lg.cli run --scraper hubner --no-use-llm
```

#### Run All Scrapers
```bash
# Default behavior - runs all scrapers
uv run python -m src.laser_ci_lg.cli run
```

## Name Matching

The scraper selection is flexible and case-insensitive:

- **Case Insensitive**: `coherent`, `Coherent`, `COHERENT` all work
- **With Extension**: `coherent.py` is automatically handled
- **Partial Matching**: The filter checks if the name is contained in the vendor name
- **Aliases**: Alternative names for convenience (e.g., `cobolt` for Hübner)

## Error Handling

If you specify an invalid scraper name, you'll see:

```
No scrapers matched filter: 'invalid'

Available scrapers:
  - coherent
  - hubner (or cobolt)
  - omicron (or luxx)
  - oxxius (or lbx)
```

## Implementation Details

### How It Works

1. **Filter Check**: The `should_run_scraper()` function in `crawler.py` checks if a vendor should be processed
2. **Name Normalization**: Names are converted to lowercase and `.py` extensions are removed
3. **Mapping Logic**: A dictionary maps aliases to vendor names
4. **Vendor Selection**: Only matching vendors are instantiated and run

### Code Structure

```python
# In crawler.py
def should_run_scraper(vendor_name: str, scraper_filter: str) -> bool:
    """Check if a scraper should run based on the filter"""
    # Normalization and matching logic
    
# In CLI
--scraper parameter -> GraphState.scraper_filter -> run_scrapers_from_config()
```

## Use Cases

### Development & Testing
- Test changes to a specific scraper without running all
- Debug issues with a particular vendor's website
- Verify fixes for specific extraction logic

### Production
- Update only specific vendors on demand
- Run quick updates for critical vendors
- Reduce processing time when only certain data is needed

### Monitoring
- Check if a specific vendor's site structure changed
- Validate scraper functionality after website updates
- Test new extraction patterns for individual vendors

## Performance Benefits

Running individual scrapers provides:
- **Faster Execution**: ~30-60s for all vs ~10-15s for one vendor
- **Reduced API Calls**: Only processes selected vendor's PDFs with Docling
- **Focused Debugging**: Easier to trace issues with specific scrapers
- **Resource Efficiency**: Less memory and CPU usage

## Future Enhancements

Potential improvements:
1. **Multiple Selection**: `--scraper coherent,omicron`
2. **Exclude Mode**: `--exclude-scraper hubner`
3. **Regex Patterns**: `--scraper-pattern "o.*"` for Omicron and Oxxius
4. **Scraper Groups**: `--scraper-group light-engines`