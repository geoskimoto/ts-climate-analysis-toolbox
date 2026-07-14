# PNW Streamflow Climate Analysis Toolbox

Detecting climate-change signals in Pacific Northwest streamflow, snowpack, and
related time series — turning a set of research notebooks into a reusable
library and (in progress) an interactive web application.

## Status

| Layer | State |
|-------|-------|
| **`climate_core`** — consolidated analysis library | ✅ built & tested |
| **`api`** — FastAPI backend | ✅ built & tested |
| **`frontend`** — React / Plotly single-site explorer | ✅ built & verified |

The original research notebooks (`*.ipynb`) and modules (`dataIO/`,
`statisticscalculator/`, `aggregate_stats/`, `plot_collection/`) are kept as-is
for reference. New work happens in **`climate_core/`**.

## `climate_core`

A clean, tested consolidation of the original analysis code:

```
climate_core/
├── data/
│   ├── sources.py     # USGSStreamflow, NRCSSnotel, fetch_environment_canada
│   └── loader.py      # DataLoader — normalises a series for the stats layer
├── stats/
│   ├── base.py        # GeneralStatistics — water-year prep + day-of-year climatology
│   ├── streamflow.py  # Streamflow — center-of-timing, seasonal volume, peak timing
│   ├── snow.py        # Snow — SNOTEL SWE / precip trends
│   └── mk.py          # mk_to_dict — JSON-serialisable Mann-Kendall results
└── catalog/
    ├── sites.py       # SiteCatalog — 822 geocoded PNW USGS sites
    └── data/pnw_sites.csv
```

### Quick start

```python
from climate_core import USGSStreamflow, DataLoader, Streamflow, mk_to_dict
from climate_core.catalog import default_catalog

site = default_catalog().get("13340000")           # Clearwater R at Orofino, ID
raw = USGSStreamflow().get_data(sites=site.site_no,
                                start_date="1930-10-01", end_date="2024-09-30")

s = Streamflow(DataLoader(raw, "Date", "Discharge"))
s.calc_annual_runoff_threshold_day(percent=0.5)      # center-of-timing
print(mk_to_dict(s.threshold_vol_dates_mann_kendall_test))
```

### The metrics

* **Center-of-timing** (`calc_annual_runoff_threshold_day`) — the day each water
  year when 50% of annual runoff has passed. An earlier trend is the classic
  snowmelt-warming signal.
* **Seasonal volume** (`calc_runoff_bw_days`) — runoff within a window
  (e.g. summer low-flow), for detecting snow→rain regime shifts.
* **Peak timing & magnitude** (`calc_max`).
* Every metric is tested for a monotonic trend with a **Mann-Kendall** test.

Water years run 1 Oct – 30 Sep, labelled by the ending calendar year.

## Backend API (`api`)

A FastAPI service over `climate_core`. Run it locally:

```bash
uvicorn api.main:app --reload      # http://127.0.0.1:8000  (docs at /docs)
```

| Method & path | Purpose |
|---|---|
| `GET /api/health` | liveness + site count |
| `GET /api/sites?query=&state=&basin=&limit=` | list / search the catalog |
| `GET /api/sites/{site_no}` | one site's metadata |
| `POST /api/analyze` | run the full trend analysis for a site |

`POST /api/analyze` takes a site number, an optional date range, and analysis
parameters (`threshold_percent`, `alpha`, seasonal windows, peak window). It
fetches live USGS data (cached), drops incomplete water years, and returns the
climatology envelope, the per-water-year center-of-timing / volume / peak
series each with a Mann-Kendall verdict, and (optionally) the daily hydrograph
curves — everything the explorer needs, on a shared day-of-water-year axis.

## Frontend (`frontend`)

A React + Plotly single-site explorer (Vite). It talks to the backend, so run
both:

```bash
# terminal 1 — backend
uvicorn api.main:app --port 8000

# terminal 2 — frontend (Vite proxies /api to :8000)
cd frontend && npm install && npm run dev     # http://localhost:5173
```

Pick a gage on the map or from the list → the app fetches its full USGS record
and renders the **daily hydrograph** (every water year over the climatology
envelope), the **center-of-timing** and **seasonal-volume** trend charts with
Sen's-slope lines, and a row of **Mann-Kendall verdict cards**. Date range and
analysis parameters are adjustable, with a re-run button.

A **Streamflow ↔ Snowpack** toggle in the top bar switches the whole explorer to
the 426 PNW **SNOTEL** stations: the same interface then reports snow-water-
equivalent signals — **peak SWE**, **April-1 SWE**, and **melt-out date** — over
the SWE hydrograph. Snowpack is the upstream driver of streamflow, so the two
views corroborate each other (e.g. Aneroid Lake, OR shows peak SWE and April-1
SWE both in significant decline). SNOTEL station metadata carries HUC codes,
laying the groundwork for a future paired snow↔streamflow basin view.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,plots,dev]"

pytest -m "not network"   # fast, deterministic
pytest -m network         # hits live USGS/SNOTEL APIs
```
