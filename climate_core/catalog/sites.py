"""Queryable catalog of PNW USGS streamflow sites.

Replaces the scattered ``*_USGS_sites.xlsx`` / ``headwater_sites.xlsx`` files
and their positional ``.iat[0, 1]`` lookups with one normalised table and a
small accessor. Backs the web API's ``GET /sites`` and metadata lookups.

The data ships as ``data/pnw_sites.csv`` (822 sites, all geocoded from the USGS
Site Service, with drainage area and elevation where available).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

_CATALOG_PATH = Path(__file__).parent / "data" / "pnw_sites.csv"


@dataclass(frozen=True)
class Site:
    site_no: str
    name: str
    basin: str
    state: str
    lat: float | None
    long: float | None
    drainage_area_sqmi: float | None
    elevation_ft: float | None

    def to_dict(self) -> dict:
        return {
            "site_no": self.site_no,
            "name": self.name,
            "basin": self.basin,
            "state": self.state,
            "lat": self.lat,
            "long": self.long,
            "drainage_area_sqmi": self.drainage_area_sqmi,
            "elevation_ft": self.elevation_ft,
        }


def _clean(value):
    return None if pd.isna(value) else value


class SiteCatalog:
    """Load and query the PNW site catalog."""

    def __init__(self, path: str | Path = _CATALOG_PATH):
        self.path = Path(path)
        self.df = pd.read_csv(self.path, dtype={"site_no": str})

    def __len__(self) -> int:
        return len(self.df)

    def _row_to_site(self, row: pd.Series) -> Site:
        return Site(
            site_no=str(row["site_no"]),
            name=str(row["name"]),
            basin=_clean(row.get("basin")) or "",
            state=_clean(row.get("state")) or "",
            lat=_clean(row.get("lat")),
            long=_clean(row.get("long")),
            drainage_area_sqmi=_clean(row.get("drainage_area_sqmi")),
            elevation_ft=_clean(row.get("elevation_ft")),
        )

    def get(self, site_no: str) -> Site:
        """Return the :class:`Site` for ``site_no`` or raise ``KeyError``."""
        site_no = str(site_no).strip()
        match = self.df[self.df["site_no"] == site_no]
        if match.empty:
            raise KeyError(f"Site {site_no!r} not found in catalog.")
        return self._row_to_site(match.iloc[0])

    def all(self) -> list[Site]:
        return [self._row_to_site(row) for _, row in self.df.iterrows()]

    def search(
        self,
        query: str | None = None,
        state: str | None = None,
        basin: str | None = None,
    ) -> list[Site]:
        """Filter sites by free-text name substring, state, and/or basin."""
        df = self.df
        if query:
            df = df[df["name"].str.contains(query, case=False, na=False)]
        if state:
            df = df[df["state"].str.upper() == state.upper()]
        if basin:
            df = df[df["basin"].str.contains(basin, case=False, na=False)]
        return [self._row_to_site(row) for _, row in df.iterrows()]


@lru_cache(maxsize=1)
def default_catalog() -> SiteCatalog:
    """Process-wide singleton catalog (loaded once)."""
    return SiteCatalog()
