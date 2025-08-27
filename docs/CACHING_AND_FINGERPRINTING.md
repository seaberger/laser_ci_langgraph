# Caching and Fingerprinting System

## Overview

The scraping system uses intelligent caching and content fingerprinting to avoid redundant downloads and processing. Every document (HTML page or PDF) is fingerprinted using SHA-256, and PDFs are cached locally for efficient reuse. With the new search-based discovery, this system ensures we only process changed content.

## Enhanced Features (v2.0)

### 1. Search-Based Discovery Caching
- **Discovery Results**: Search results cached to avoid repeated API calls
- **Product URLs**: Discovered URLs tracked to prevent duplicates
- **Progress Tracking**: Resume discovery from interruption point

### 2. SHA-256 Content Fingerprinting
- **Unique Identification**: Every document's content hashed with SHA-256
- **Change Detection**: Only reprocess if content hash changes
- **Database Tracking**: Hashes stored for instant comparison
- **Deduplication**: Prevents storing duplicate content

### 3. Intelligent PDF Caching
- **Local Storage**: PDFs saved to `data/pdf_cache/vendor_name/`
- **Organized Structure**: Each vendor has dedicated subdirectory
- **Smart Retrieval**: Check cache before downloading
- **Docling Integration**: Cached PDFs processed with ACCURATE mode

### 4. Skip Logic Optimization
Documents are skipped when:
- Content hash matches previously processed version
- PDF exists in cache with unchanged hash
- Database contains same document with same hash
- Product already discovered in current session

### 5. Force Refresh Override
- **CLI Flag**: `--force-refresh` bypasses all caching
- **Testing**: Essential for development and debugging
- **Full Reprocessing**: Forces fresh discovery and download

## How It Works

### Discovery Phase (NEW)
```python
# DuckDuckGo search with caching
discovered_urls = set()  # Track within session

def search_vendor_products(vendor, patterns):
    for pattern in patterns:
        query = f'site:{vendor.domain} "{pattern}" laser'
        results = ddgs.text(query)
        
        for result in results:
            if result.url not in discovered_urls:
                discovered_urls.add(result.url)
                yield result
```

### Content Processing
```python
def process_document(url, content):
    # Calculate fingerprint
    content_hash = hashlib.sha256(content).hexdigest()
    
    # Check database for existing
    existing = db.query(RawDocument).filter_by(
        url=url,
        content_hash=content_hash
    ).first()
    
    if existing and not force_refresh:
        print(f"✓ Unchanged: {url}")
        return  # Skip processing
    
    # Process new/changed content
    extract_specs(content)
```

## Directory Structure

```
data/
├── laser-ci.sqlite              # Database with hashes
├── discovery_progress.json      # Discovery state (resumable)
└── pdf_cache/                   # Cached PDFs
    ├── coherent/
    │   ├── obis-family-ds.pdf
    │   ├── cellx-ds.pdf
    │   └── galaxy-ds.pdf
    ├── hubner_photonics_cobolt/
    │   ├── cobolt-06-01-series.pdf
    │   └── cobolt-05-01-series.pdf
    ├── omicron/
    │   ├── luxx_plus_datasheet.pdf
    │   └── brixx_datasheet.pdf
    ├── oxxius/
    │   ├── lbx-375-datasheet.pdf
    │   └── lcx-datasheet.pdf
    └── lumencor/
        ├── celesta-datasheet.pdf
        └── spectra-datasheet.pdf
```

## Database Schema

Enhanced with content tracking:
```python
class RawDocument:
    url: str                # Document URL
    content_hash: str       # SHA-256 hash
    file_path: str         # Cache location
    raw_specs: dict        # Extracted specs
    fetched_at: datetime   # Timestamp
    
    # Unique constraint on (url, content_hash)
```

## Performance Benefits

### Expected Benefits
- **Network Efficiency**: Search API uses less bandwidth than full page downloads
- **Cached PDFs**: Download once, reuse on subsequent runs
- **Skip Unchanged**: No redundant processing of unchanged content
- **Faster Iterations**: Cached runs should be significantly faster

*Note: Actual performance metrics will be collected during production use.*

### Storage Efficiency
- **Deduplicated Content**: Same hash = no duplicate storage
- **Compressed Cache**: PDFs stored efficiently
- **Clean Structure**: Organized by vendor

## CLI Usage

### Normal Run (Uses Cache)
```bash
uv run python -m src.laser_ci_lg.cli run
```

Output:
```
🔍 Discovering Coherent
  Using cached discovery results
  ✓ 20 products found (cached)
  
Processing OBIS-family-ds.pdf
  → Cache hit: data/pdf_cache/coherent/obis-family-ds.pdf
  → Hash match: content unchanged
  ✓ Skipped (no changes detected)
```

### Force Refresh
```bash
uv run python -m src.laser_ci_lg.cli run --force-refresh
```

Output:
```
🔍 Discovering Coherent (forced refresh)
  Searching: "OBIS" laser...
  ✓ 20 products discovered
  
Processing OBIS-family-ds.pdf
  → Downloading fresh copy
  → Extracting with Docling ACCURATE mode
  ✓ 1619 specs extracted
```

### Check Cache Status
```bash
# View cache statistics
ls -lah data/pdf_cache/*/ | wc -l  # Count cached PDFs
du -sh data/pdf_cache/              # Total cache size

# Database statistics
sqlite3 data/laser-ci.sqlite \
  "SELECT COUNT(DISTINCT content_hash) FROM raw_documents"
```

## Advanced Features

### Resumable Discovery
Discovery progress saved for interruption recovery:
```json
{
  "completed_vendors": ["Coherent", "Omicron"],
  "completed_patterns": {
    "Oxxius": ["LBX", "LBX-375", "LBX-405"]
  },
  "timestamp": "2024-03-15T10:30:00"
}
```

### Incremental Updates
Only process changes since last run:
```python
# Check last run timestamp
last_run = get_last_run_timestamp()

# Only process if changed after last run
if document.last_modified > last_run:
    process_document(document)
```

### Smart PDF Detection
Automatically identifies PDF URLs:
```python
def is_pdf_url(url):
    return (
        url.lower().endswith('.pdf') or
        'datasheet' in url.lower() or
        'download/pdf' in url.lower()
    )
```

## Configuration

### Cache Settings
```python
# In unified_base.py
CACHE_DIR = Path("data/pdf_cache")
ENABLE_CACHE = True
MAX_CACHE_AGE_DAYS = 30  # Optional TTL
```

### Environment Variables
```bash
CACHE_ENABLED=true          # Enable/disable caching
CACHE_DIR=/path/to/cache   # Custom cache location
FORCE_REFRESH=false         # Override via environment
```

## Troubleshooting

### Cache Issues

**Problem**: Old cached data being used
```bash
# Solution: Clear specific vendor cache
rm -rf data/pdf_cache/vendor_name/

# Or force refresh
uv run python -m src.laser_ci_lg.cli run --force-refresh
```

**Problem**: Cache growing too large
```bash
# Solution: Clean old cache files
find data/pdf_cache -mtime +30 -delete  # Remove >30 days old
```

**Problem**: Hash mismatches
```bash
# Solution: Recalculate hashes
uv run python -m src.laser_ci_lg.cli clean vendor_name
uv run python -m src.laser_ci_lg.cli run --scraper vendor_name
```

### Database Issues

**Problem**: Duplicate entries
```sql
-- Find duplicates
SELECT url, content_hash, COUNT(*) 
FROM raw_documents 
GROUP BY url, content_hash 
HAVING COUNT(*) > 1;

-- Remove duplicates (keep newest)
DELETE FROM raw_documents 
WHERE id NOT IN (
  SELECT MAX(id) 
  FROM raw_documents 
  GROUP BY url, content_hash
);
```

## Potential Future Enhancements

- [ ] **Redis Cache**: Distributed caching for team use
- [ ] **Smart Expiry**: TTL based on vendor update frequency
- [ ] **Delta Detection**: Track which specs actually changed between runs

## Summary

The caching and fingerprinting system provides:
- Reduced bandwidth usage through intelligent caching
- Faster pipeline execution on cached runs
- No duplicate processing with SHA-256 fingerprinting
- Resumable operations for interrupted discoveries
- Organized storage with vendor-specific directories

Combined with search-based discovery, this system ensures efficient, fast, and reliable competitive intelligence gathering.