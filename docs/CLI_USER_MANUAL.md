# CLI User Manual

## Overview

The LASER-CI-LG command-line interface provides comprehensive control over the competitive intelligence pipeline. All commands are accessed through the main `cli.py` module.

**v2.0 Updates**: The pipeline now uses DuckDuckGo search for product discovery, enabling faster and more reliable discovery. Features include individual SKU extraction and improved normalization with parallel LLM processing.

## Installation & Setup

### Prerequisites

1. **Install Dependencies**:
   ```bash
   uv venv
   uv pip install -r requirements.txt
   ```

2. **Configure OpenAI API Key**:
   ```bash
   echo "OPENAI_API_KEY=sk-..." > .env
   ```

3. **Verify Installation**:
   ```bash
   uv run python -m src.laser_ci_lg.cli --help
   ```

## Command Reference

### 1. `run` - Execute Pipeline

Runs the complete competitive intelligence pipeline including discovery, extraction, normalization, and reporting.

```bash
uv run python -m src.laser_ci_lg.cli run [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--model` | TEXT | None | OpenAI model to use (e.g., gpt-4o-mini, gpt-4o) |
| `--use-llm/--no-llm` | BOOL | True | Enable/disable LLM for spec normalization |
| `--config-path` | PATH | config/competitors.yml | Path to configuration file |
| `--force-refresh` | BOOL | False | Force re-download all documents |
| `--scraper` | TEXT | None | Run specific vendor only |

#### Examples

**Run complete pipeline**:
```bash
uv run python -m src.laser_ci_lg.cli run
```

**Run with specific OpenAI model**:
```bash
uv run python -m src.laser_ci_lg.cli run --model gpt-4o
```

**Run without LLM enhancement** (heuristics only):
```bash
uv run python -m src.laser_ci_lg.cli run --no-llm
```

**Force refresh all data** (bypass cache):
```bash
uv run python -m src.laser_ci_lg.cli run --force-refresh
```

**Run specific scraper only**:
```bash
# Single vendor scrapers
uv run python -m src.laser_ci_lg.cli run --scraper coherent
uv run python -m src.laser_ci_lg.cli run --scraper omicron
uv run python -m src.laser_ci_lg.cli run --scraper oxxius
uv run python -m src.laser_ci_lg.cli run --scraper lumencor

# Vendor aliases (alternative names)
uv run python -m src.laser_ci_lg.cli run --scraper hubner  # Hübner Photonics
uv run python -m src.laser_ci_lg.cli run --scraper cobolt  # Also Hübner
uv run python -m src.laser_ci_lg.cli run --scraper luxx    # Omicron LuxX
uv run python -m src.laser_ci_lg.cli run --scraper lbx     # Oxxius LBX
```

**Combine options**:
```bash
uv run python -m src.laser_ci_lg.cli run --scraper coherent --force-refresh --model gpt-4o
```

#### Output

The command displays:
1. Discovery progress (products found via search)
2. Extraction statistics per vendor  
3. Normalization results (heuristic vs LLM)
4. Generated competitive report
5. Benchmark comparison table
6. Processing time and efficiency metrics

### 2. `schedule` - Schedule Periodic Runs

Sets up automated pipeline execution using cron scheduling.

```bash
uv run python -m src.laser_ci_lg.cli schedule [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cron` | TEXT | "3 10 1 * *" | Cron expression (M H DOM MON DOW) |
| `--model` | TEXT | None | OpenAI model for scheduled runs |
| `--use-llm/--no-llm` | BOOL | True | Enable/disable LLM |
| `--config-path` | PATH | config/competitors.yml | Configuration file |

#### Cron Format

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday = 0)
│ │ │ │ │
* * * * *
```

#### Examples

**Default monthly schedule** (3:10 AM on 1st of month):
```bash
uv run python -m src.laser_ci_lg.cli schedule
```

**Weekly schedule** (Mondays at 9 AM):
```bash
uv run python -m src.laser_ci_lg.cli schedule --cron "0 9 * * 1"
```

**Daily schedule** (2:30 AM every day):
```bash
uv run python -m src.laser_ci_lg.cli schedule --cron "30 2 * * *"
```

**Monthly with specific model**:
```bash
uv run python -m src.laser_ci_lg.cli schedule --cron "0 4 1 * *" --model gpt-4o
```

#### Output

- Creates timestamped reports in `reports/` directory
- Format: `reports/YYYY-MM-report.md`
- Runs continuously until interrupted (Ctrl+C)

### 3. `clean` - Clean Vendor Data

Removes cached and database data for specific vendors.

```bash
uv run python -m src.laser_ci_lg.cli clean VENDOR [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `VENDOR` | Yes | Vendor name to clean |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cache/--no-cache` | BOOL | True | Clean PDF cache files |
| `--database/--no-database` | BOOL | True | Clean database entries |
| `--dry-run` | BOOL | False | Preview without deleting |

#### Supported Vendors

- `coherent` - Coherent lasers
- `hubner` or `cobolt` - Hübner Photonics (Cobolt)
- `omicron` or `luxx` - Omicron LuxX lasers
- `oxxius` or `lbx` - Oxxius LBX lasers
- `lumencor` - Lumencor light engines

#### Examples

**Clean all data for vendor**:
```bash
uv run python -m src.laser_ci_lg.cli clean omicron
```

**Preview what would be deleted** (dry run):
```bash
uv run python -m src.laser_ci_lg.cli clean oxxius --dry-run
```

**Clean only PDF cache**:
```bash
uv run python -m src.laser_ci_lg.cli clean hubner --no-database
```

**Clean only database**:
```bash
uv run python -m src.laser_ci_lg.cli clean coherent --no-cache
```

#### Output

Shows:
- Number of PDF files in cache
- Number of products and documents in database
- Confirmation of deletion (or dry-run preview)

### 4. `list-vendors` - List Database Contents

Displays all vendors with their data statistics.

```bash
uv run python -m src.laser_ci_lg.cli list-vendors
```

#### No Options

This command takes no options.

#### Examples

```bash
uv run python -m src.laser_ci_lg.cli list-vendors
```

#### Output

Displays a formatted table:

```
+------------------------+----------+-----------+-----------+-------------+
| Vendor                 | Products | HTML Docs | PDF Docs  | Cached PDFs |
+========================+==========+===========+===========+=============+
| Coherent               | 15       | 10        | 5         | 5           |
| Hübner Photonics       | 8        | 4         | 4         | 4           |
| Omicron                | 12       | 8         | 4         | 4           |
| Oxxius                 | 10       | 6         | 4         | 4           |
| Lumencor               | 7        | 7         | 0         | 0           |
+------------------------+----------+-----------+-----------+-------------+
```

## Common Workflows

### Initial Setup and Run

```bash
# 1. Install and configure
uv venv
uv pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env

# 2. Run full pipeline
uv run python -m src.laser_ci_lg.cli run

# 3. Review results
cat competitive_intelligence_report.md
```

### Testing New Scraper

```bash
# 1. Clean existing data
uv run python -m src.laser_ci_lg.cli clean newvendor

# 2. Run scraper with forced refresh
uv run python -m src.laser_ci_lg.cli run --scraper newvendor --force-refresh

# 3. Check extraction results
uv run python -m src.laser_ci_lg.cli list-vendors
```

### Production Deployment

```bash
# 1. Test run with production model
uv run python -m src.laser_ci_lg.cli run --model gpt-4o

# 2. Schedule monthly runs
uv run python -m src.laser_ci_lg.cli schedule --cron "0 3 1 * *" --model gpt-4o

# 3. Monitor reports directory
ls -la reports/
```

### Troubleshooting Extraction

```bash
# 1. Run without LLM to test heuristics
uv run python -m src.laser_ci_lg.cli run --scraper problematic_vendor --no-llm

# 2. Force refresh to bypass cache
uv run python -m src.laser_ci_lg.cli run --scraper problematic_vendor --force-refresh

# 3. Clean and retry
uv run python -m src.laser_ci_lg.cli clean problematic_vendor
uv run python -m src.laser_ci_lg.cli run --scraper problematic_vendor
```

## Environment Variables

The CLI respects these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM features | Required for LLM |
| `OPENAI_MODEL` | Default model if not specified | gpt-4o-mini |
| `DATABASE_URL` | SQLite database path | data/laser-ci.sqlite |

## File Locations

| Directory/File | Purpose |
|---------------|---------|
| `data/laser-ci.sqlite` | Main database |
| `data/pdf_cache/` | Cached PDF files by vendor |
| `reports/` | Generated reports |
| `config/competitors.yml` | Vendor/product configuration |
| `config/segments.yml` | Market segment definitions |
| `.env` | Environment variables |

## Error Handling

### Common Errors and Solutions

**"OPENAI_API_KEY not set"**:
- Create `.env` file with your API key
- Or export: `export OPENAI_API_KEY=sk-...`

**"No vendor found matching 'X'"**:
- Check vendor name spelling
- Use `list-vendors` to see available vendors
- Try vendor aliases (e.g., 'hubner' or 'cobolt')

**"Connection timeout"**:
- Vendor site may be slow/down
- Try `--force-refresh` to bypass cache
- Check internet connection

**"PDF extraction failed"**:
- PDF may be image-based (not text)
- Try cleaning cache and re-running
- Check if PDF URL is valid

## Performance Tips

1. **Use specific scrapers** during development:
   ```bash
   uv run python -m src.laser_ci_lg.cli run --scraper vendor_name
   ```

2. **Avoid --force-refresh** unless necessary:
   - Uses cached data when unchanged
   - Reduces API calls and bandwidth

3. **Run without LLM** for faster testing:
   ```bash
   uv run python -m src.laser_ci_lg.cli run --no-llm
   ```

4. **Clean selectively**:
   - Keep PDF cache during testing
   - Only clean database when schema changes

## Getting Help

```bash
# Main help
uv run python -m src.laser_ci_lg.cli --help

# Command-specific help
uv run python -m src.laser_ci_lg.cli run --help
uv run python -m src.laser_ci_lg.cli schedule --help
uv run python -m src.laser_ci_lg.cli clean --help
uv run python -m src.laser_ci_lg.cli list-vendors --help
```

## Summary

The CLI provides complete control over the LASER-CI-LG pipeline:
- **`run`** - Execute pipeline with flexible options
- **`schedule`** - Automate periodic execution
- **`clean`** - Manage cached and database data
- **`list-vendors`** - Monitor extraction status

For technical details, see [LASER-CI-LG_THEORY_OF_OPERATION.md](./LASER-CI-LG_THEORY_OF_OPERATION.md).