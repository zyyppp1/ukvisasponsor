# UK Visa Sponsor Checker

Tell instantly whether a UK company can sponsor a Skilled Worker visa — by matching
a job listing's company name against the Home Office's official register of licensed
sponsors, and surfacing salary thresholds and sponsorship insight alongside it.

This is a portfolio project built to be explained end-to-end in interviews. The
engineering centre of gravity is the **backend**: a company-name matching service
(record linkage / entity resolution) over ~143k official records, exposed as an API,
backed by Postgres, and delivered through a lightweight Chrome extension.

## The problem

A job seeker who needs visa sponsorship cannot tell, from a LinkedIn or Indeed
listing, whether the employer actually holds a sponsor licence. The data to answer
this is public but unusable at a glance: the Home Office register has ~143k rows and
the company names never match what a job board displays.

- `J.P. Morgan` → **0** naive substring hits (the register spells it differently) — a *miss*.
- `Revolut` → **15** substring hits, but only `Revolut Ltd` is the fintech; the rest are
  "Revolution …" companies — *false matches*.
- `Monzo Bank Ltd` appears **3×**; `Google` is listed as `Google (UK) Limited`.

The core task is turning a messy, human-typed company name into the right official
sponsor record — reliably, at scale, trading off **precision vs recall**.

## Data source

[Register of licensed sponsors: workers](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers)
— UK Home Office, public, updated nearly every business day. ~143k rows, 5 columns:
Organisation Name, Town/City, County, Type & Rating, Route. No scraping, no guessing.

Run `python scripts/download_register.py` to fetch today's copy (the URL changes daily).

## Roadmap

| Phase | What | Status |
|------:|------|--------|
| 0 | Acquire & profile the register | ✅ done |
| 1 | Company-name matcher in pure Python + tests (normalize → exact → fuzzy) | 🚧 in progress |
| 2 | Expose the matcher as a FastAPI service | ⬜ |
| 3 | Move data into Postgres; index for fast lookup | ⬜ |
| 4 | Minimal Chrome extension: scrape company name → call the API | ⬜ |
| 5 | Deploy (Fly.io) | ⬜ |
| 6 | AI enhancement: embedding-based semantic matching + LLM entity disambiguation | ⬜ |

Secondary narratives layered on the same data:
- **Data Engineering** — turn the daily-updating source into a real ingestion pipeline
  (fetch → validate → clean → dedupe → load → daily snapshots for a self-built time series).
- **Data Analysis / BI** — a Power BI / Tableau dashboard: sponsor density by location,
  rankings, rating/route distribution, and trends derived from the daily snapshots.

## Tech stack

- **Core / backend:** Python, FastAPI, Postgres, RapidFuzz (fuzzy matching), pytest
- **Extension:** Manifest V3, TypeScript / vanilla JS (kept deliberately thin)
- **AI (Phase 6):** text embeddings for semantic matching, an LLM for entity disambiguation
- **BI:** Power BI / Tableau on the Postgres warehouse

## Project layout

```
ukvisasponsor/
├── data/            # the register CSV (gitignored; fetch with the download script)
├── matcher/         # the matching library (the heart of the project)
├── tests/           # unit tests, cases derived from real dirty-data examples
├── scripts/         # data download / pipeline scripts
├── notebooks/       # exploratory data analysis (DA layer)
├── dashboard/       # Power BI / Tableau artifacts (DA layer)
└── NOTES.md         # development log + interview prep, per phase
```

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_register.py   # fetch today's register into data/
pytest                                # run the test suite
```
