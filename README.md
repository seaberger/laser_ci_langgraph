# Laser CI – LangGraph + OpenAI

An agentic pipeline built on **LangGraph** using **OpenAI** to:
- Crawl manufacturer sites (HTML/PDF) for **diode/instrumentation lasers** and **light engines**
- Normalize heterogeneous spec names into a canonical schema (heuristics + LLM fallback)
- Snapshot to **SQLite**, detect **new entrants** and **spec deltas**
- Benchmark competitors vs **Coherent** models
- Run **monthly** via APScheduler/cron

competitive-intel/
├── README.md
├── requirements.txt
├── config/
│   ├── segments.yml
│   └── competitors.yml
├── src/laser_ci_lg/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   ├── specs.py
│   ├── llm.py
│   ├── scrapers/
│   │   ├── base.py
│   │   ├── coherent.py
│   │   ├── hubner_cobolt.py
│   │   ├── omicron_luxx.py
│   │   └── oxxius_lbx.py
│   ├── crawler.py
│   ├── normalize.py
│   ├── reporter.py
│   ├── benchmark.py
│   ├── graph.py
│   └── cli.py
└── data/               # created at runtime

## Setup
```bash
# Install uv if not already installed
# curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt

# Create .env file with your OpenAI API key
echo "OPENAI_API_KEY=sk-..." > .env
# optional: echo "OPENAI_MODEL=gpt-4o-mini" >> .env

# Run commands with uv
uv run python -m src.laser_ci_lg.cli --help

# Run specific scraper
uv run python -m src.laser_ci_lg.cli run --scraper coherent

# Force refresh for specific vendor
uv run python -m src.laser_ci_lg.cli run --scraper hubner --force-refresh

---

## Notes / Implementation choices (why this will work for you)

- **Spec Reasoning Agent (LLM)**: Uses OpenAI **structured JSON** (`response_format: json_schema`) to guarantee well-formed canonical outputs, avoiding brittle regex-only pipelines when vendors rename fields.
- **Heuristic-first, LLM-second**: You won’t pay the LLM tax if the PDF/HTML parse yields enough mapped specs; the LLM only triggers if <4 canonical fields are populated.
- **LangGraph**: Graph keeps stages isolated and composable. You can add branches (e.g., alerting via Slack/Email) as new nodes without touching the rest.
- **SQLite snapshots**: Every normalize pass writes a new `NormalizedSpec` snapshot; your **monthly diffs** are straightforward and auditable.
- **Bench buckets**: Wavelength rounding + power classes surfaces practical head-to-heads (e.g., 488 nm @ 100 mW class).

---

### Next upgrades (fast wins)

- **Parallel fetch**: Wrap scraper calls in async (e.g., `httpx` + tasks) and add a LangGraph map-style node if your target count grows.
- **Vendor-specific parsers**: A few lines of BeautifulSoup rules per vendor will boost k/v extraction (e.g., Omicron tables, Cobolt PDF tables).
- **Light-engine schema**: Add fields for `channels`, `combiner loss`, `fiber type`, `total output` for Galaxy/CellX comparability.
- **Change alerts**: Add a node to post delta summaries to Slack or email when `Δ` thresholds trigger.

---

If you want, I can add a **Vortran Stradus** and **Thorlabs DJ** scraper module and expand the canonical schema for **driver I/O / interlocks** and **warranty**.