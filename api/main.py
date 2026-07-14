"""FastAPI app for the PNW streamflow climate explorer.

Run locally:
    uvicorn api.main:app --reload

Routes (all under /api):
    GET  /health
    GET  /sites            list / search the site catalog
    GET  /sites/{site_no}  one site's metadata
    POST /analyze          run the trend analysis for a site
"""

from __future__ import annotations

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api import schemas, service, service_snow
from climate_core.catalog import default_catalog, default_snotel_catalog

app = FastAPI(
    title="PNW Streamflow Climate Analysis API",
    version="0.1.0",
    description="Detect climate-change signals (center-of-timing, seasonal "
    "volume, peak) in Pacific Northwest streamflow via Mann-Kendall trend tests.",
)

# Local-only tool: allow the Vite/CRA dev servers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "sites": len(default_catalog()),
        "snotel_sites": len(default_snotel_catalog()),
    }


@app.get("/api/sites", response_model=list[schemas.SiteOut])
def list_sites(
    query: str | None = Query(None, description="Case-insensitive name substring."),
    state: str | None = Query(None, description="WA | OR | ID."),
    basin: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> list[schemas.SiteOut]:
    catalog = default_catalog()
    sites = catalog.search(query=query, state=state, basin=basin) if (query or state or basin) else catalog.all()
    return [schemas.SiteOut(**s.to_dict()) for s in sites[:limit]]


@app.get("/api/sites/{site_no}", response_model=schemas.SiteOut)
def get_site(site_no: str) -> schemas.SiteOut:
    try:
        site = default_catalog().get(site_no)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Site {site_no!r} not found.")
    return schemas.SiteOut(**site.to_dict())


@app.post("/api/analyze", response_model=schemas.AnalysisResult)
def analyze(req: schemas.AnalysisRequest) -> schemas.AnalysisResult:
    try:
        return service.run_analysis(req)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Site {req.site_no!r} not found.")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Upstream data source error: {e}")


@app.get("/api/snotel-sites", response_model=list[schemas.SnotelSiteOut])
def list_snotel_sites(
    query: str | None = Query(None, description="Case-insensitive name substring."),
    state: str | None = Query(None, description="OR | WA | ID | MT | WY."),
    limit: int = Query(1000, ge=1, le=2000),
) -> list[schemas.SnotelSiteOut]:
    catalog = default_snotel_catalog()
    stations = catalog.search(query=query, state=state) if (query or state) else catalog.all()
    return [schemas.SnotelSiteOut(**s.to_dict()) for s in stations[:limit]]


@app.post("/api/analyze/snow", response_model=schemas.SnowAnalysisResult)
def analyze_snow(req: schemas.SnowAnalysisRequest) -> schemas.SnowAnalysisResult:
    try:
        return service_snow.run_snow_analysis(req)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"SNOTEL station {req.station_triplet!r} not found.")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Upstream data source error: {e}")
