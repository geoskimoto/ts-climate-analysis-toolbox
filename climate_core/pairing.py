"""Suggest SNOTEL stations that plausibly represent a streamflow gage's basin.

This is deliberately a *suggestion* tool, not an authoritative spatial join.
Correctly determining which snow stations drain to a gage needs basin-boundary
polygons; here we approximate with three cheap, transparent signals and hand the
ranked shortlist to a human to curate (this is option "B"'s honesty guarantee):

    1. HUC match  -- SNOTEL is in the same 8-digit hydrologic unit as the gage
                     (SNOTEL HUCs are 12-digit; compare the first 8).
    2. Elevation  -- snow sources sit *above* the gage, so keep stations higher
                     than the gage (skipped when the gage elevation is unknown).
    3. Proximity  -- rank by great-circle distance from the gage.

Each candidate is returned with the signals that placed it there, so the person
choosing can see *why* it was suggested and reject bad matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from climate_core.catalog import default_catalog, default_snotel_catalog
from climate_core.catalog.sites import Site
from climate_core.catalog.snotel import SnotelStation


def _haversine_miles(lat1, lon1, lat2, lon2) -> float:
    r = 3958.8  # earth radius, miles
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


@dataclass(frozen=True)
class SnotelCandidate:
    station: SnotelStation
    distance_miles: float
    elevation_diff_ft: float | None  # station elevation minus gage elevation
    same_huc8: bool

    def to_dict(self) -> dict:
        return {
            **self.station.to_dict(),
            "distance_miles": round(self.distance_miles, 1),
            "elevation_diff_ft": None if self.elevation_diff_ft is None else round(self.elevation_diff_ft),
            "same_huc8": self.same_huc8,
        }


def suggest_snotel_for_gage(
    site_no: str,
    max_candidates: int = 6,
    require_higher: bool = True,
    max_distance_miles: float = 60.0,
) -> list[SnotelCandidate]:
    """Return a ranked shortlist of SNOTEL stations to consider pairing with the
    gage ``site_no``. Ordered best-first (same HUC8 and nearest rank highest).

    Raises ``KeyError`` if the gage is not in the catalog.
    """
    gage: Site = default_catalog().get(site_no)
    if gage.lat is None or gage.long is None:
        return []

    gage_huc8 = (gage.huc or "")[:8]
    candidates: list[SnotelCandidate] = []

    for st in default_snotel_catalog().all():
        if st.lat is None or st.long is None:
            continue
        elev_diff = (
            None if (st.elevation_ft is None or gage.elevation_ft is None)
            else st.elevation_ft - gage.elevation_ft
        )
        if require_higher and elev_diff is not None and elev_diff <= 0:
            continue

        dist = _haversine_miles(gage.lat, gage.long, st.lat, st.long)
        if dist > max_distance_miles:
            continue

        same_huc8 = bool(gage_huc8) and str(st.huc or "").startswith(gage_huc8)
        candidates.append(SnotelCandidate(st, dist, elev_diff, same_huc8))

    # Same-HUC8 stations first, then by ascending distance.
    candidates.sort(key=lambda c: (not c.same_huc8, c.distance_miles))
    return candidates[:max_candidates]
