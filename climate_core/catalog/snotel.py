"""Queryable catalog of PNW SNOTEL snow-monitoring stations.

Mirrors :mod:`climate_core.catalog.sites` (the USGS gage catalog). Each station
carries its coordinates, elevation, record span, and **HUC code** — the HUC is
what a future paired snow↔streamflow view will use to associate a station with
the basin of a downstream gage (see the project's option "B").

Ships as ``data/snotel_sites.csv`` (426 stations across OR/WA/ID/MT/WY, all
geocoded from the NRCS AWDB metadata API).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

_CATALOG_PATH = Path(__file__).parent / "data" / "snotel_sites.csv"


@dataclass(frozen=True)
class SnotelStation:
    station_triplet: str
    station_id: str
    name: str
    state: str
    lat: float | None
    long: float | None
    elevation_ft: float | None
    huc: str | None
    begin_date: str | None
    end_date: str | None

    def to_dict(self) -> dict:
        return {
            "station_triplet": self.station_triplet,
            "station_id": self.station_id,
            "name": self.name,
            "state": self.state,
            "lat": self.lat,
            "long": self.long,
            "elevation_ft": self.elevation_ft,
            "huc": self.huc,
            "begin_date": self.begin_date,
            "end_date": self.end_date,
        }


def _clean(value):
    return None if pd.isna(value) else value


class SnotelCatalog:
    """Load and query the PNW SNOTEL station catalog."""

    def __init__(self, path: str | Path = _CATALOG_PATH):
        self.path = Path(path)
        self.df = pd.read_csv(self.path, dtype={"station_triplet": str, "station_id": str, "huc": str})

    def __len__(self) -> int:
        return len(self.df)

    def _row(self, row: pd.Series) -> SnotelStation:
        return SnotelStation(
            station_triplet=str(row["station_triplet"]),
            station_id=str(row["station_id"]),
            name=str(row["name"]),
            state=_clean(row.get("state")) or "",
            lat=_clean(row.get("lat")),
            long=_clean(row.get("long")),
            elevation_ft=_clean(row.get("elevation_ft")),
            huc=_clean(row.get("huc")),
            begin_date=_clean(row.get("begin_date")),
            end_date=_clean(row.get("end_date")),
        )

    def get(self, triplet: str) -> SnotelStation:
        """Return the station for ``triplet`` (e.g. '302:OR:SNTL') or raise ``KeyError``."""
        triplet = str(triplet).strip()
        match = self.df[self.df["station_triplet"] == triplet]
        if match.empty:
            raise KeyError(f"SNOTEL station {triplet!r} not found in catalog.")
        return self._row(match.iloc[0])

    def all(self) -> list[SnotelStation]:
        return [self._row(row) for _, row in self.df.iterrows()]

    def search(self, query: str | None = None, state: str | None = None) -> list[SnotelStation]:
        df = self.df
        if query:
            df = df[df["name"].str.contains(query, case=False, na=False)]
        if state:
            df = df[df["state"].str.upper() == state.upper()]
        return [self._row(row) for _, row in df.iterrows()]

    def by_huc(self, huc_prefix: str) -> list[SnotelStation]:
        """Stations whose HUC starts with ``huc_prefix`` — the basis for future
        basin-based pairing with streamflow gages.
        """
        mask = self.df["huc"].astype(str).str.startswith(str(huc_prefix))
        return [self._row(row) for _, row in self.df[mask].iterrows()]


@lru_cache(maxsize=1)
def default_snotel_catalog() -> SnotelCatalog:
    return SnotelCatalog()
