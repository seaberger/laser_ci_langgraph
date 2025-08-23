# Duplicate Document Handling

## Overview
The scraper system implements comprehensive duplicate prevention and update logic to ensure data integrity while supporting content updates.

## How It Works

### 1. Content Fingerprinting
- Every document (HTML page or PDF) is fingerprinted using SHA-256 hash
- The hash is stored in the `content_hash` field in the database
- This allows detection of content changes even for the same URL

### 2. Duplicate Prevention Logic

The `store_document()` method in `BaseScraper` implements three-tier logic:

#### Case 1: Unchanged Content (Same URL, Same Hash)
- **Action**: Skip insertion
- **Message**: "Document unchanged, skipping database insert"
- **Use Case**: When content hasn't changed since last fetch

#### Case 2: Changed Content (Same URL, Different Hash)
- **Action**: Update existing document
- **Message**: "Content changed, updating existing document"
- **Use Case**: When website/PDF content has been updated
- **Updates**: All fields including text, specs, hash, and timestamp

#### Case 3: New Document (New URL)
- **Action**: Insert new document
- **Message**: "Storing new document"
- **Use Case**: First time fetching a URL

### 3. Force Refresh Behavior

When `--force-refresh` flag is used:
- PDFs are re-downloaded from the network (bypassing cache)
- Content is re-processed through Docling
- If content hasn't changed (same hash), database insert is still skipped
- If content has changed, existing document is updated (not duplicated)

### 4. Database Schema

```sql
CREATE TABLE raw_documents (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    url VARCHAR(500) NOT NULL,
    content_hash VARCHAR(64),  -- SHA-256 hash
    file_path VARCHAR(500),     -- Local PDF cache path
    fetched_at DATETIME NOT NULL,
    -- other fields...
)
```

## Benefits

1. **No Duplicates**: Same URL never appears multiple times in database
2. **Change Detection**: Only processes changed content
3. **Update Tracking**: `fetched_at` shows when content last changed
4. **Network Efficiency**: Cached PDFs reduce unnecessary downloads
5. **Processing Efficiency**: Skip Docling processing for unchanged PDFs

## Testing

Test the duplicate handling:

```bash
# First run - downloads and stores documents
uv run python -m src.laser_ci_lg.cli run --scraper coherent

# Second run - skips unchanged documents
uv run python -m src.laser_ci_lg.cli run --scraper coherent

# Force refresh - re-checks but still prevents duplicates
uv run python -m src.laser_ci_lg.cli run --scraper coherent --force-refresh
```

Check for duplicates in database:
```sql
-- Should return 0 rows if no duplicates exist
SELECT url, COUNT(*) as count
FROM raw_documents
GROUP BY url
HAVING COUNT(*) > 1;
```

## Implementation Details

All scrapers inherit the `store_document()` method from `BaseScraper`:

```python
def store_document(self, session, target, status, content_type, 
                  text, content_hash, file_path, raw_specs):
    # Check for same URL + same hash (unchanged)
    # Check for same URL + different hash (updated)
    # Insert only if truly new
```

This ensures consistent duplicate handling across all vendor scrapers.