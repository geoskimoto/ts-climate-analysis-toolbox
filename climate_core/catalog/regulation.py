"""Name/size heuristic for flow regulation of a USGS gage.

This is a screening hint only: it looks at the station name and the drainage
area and is NOT a verified determination of regulation.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REGULATED = "regulated"
LIKELY_REGULATED = "likely_regulated"
LIKELY_UNREGULATED = "likely_unregulated"
UNKNOWN = "unknown"

SMALL_BASIN_SQMI = 200.0   # below this (and > 0) the basin is "likely unregulated"

_REGULATED_PATH = Path(__file__).parent / "data" / "regulated_gauges.csv"
_COLUMNS = ("site_no", "name", "regulator", "kind", "confidence", "source_url")
_KINDS = {"dam_release", "diversion", "reservoir_storage", "canal_or_return_flow", "multiple"}
_CONFIDENCES = {"high", "medium"}
_HTTP = re.compile(r"^https?://\S+$")

_NOTE = "Name/size heuristic, not verified."

# Word-boundary patterns on the upper-cased station name, checked in order.
_REGULATED_PATTERNS = [
    re.compile(p)
    for p in (
        r"\bDAM\b",
        r"\bBELOW\b",
        r"\bBL\b",
        r"\bRESERVOIRS?\b",
        r"\bCANALS?\b",
        r"\bDIVERSIONS?\b",
        r"\bFLUMES?\b",
        r"\bLAKE\s+OUTLET\b",
        r"\bWASTEWAY\b",
        r"\bOUTLET\s+OF\b.*?\b(?:LAKE|RESERVOIR)\b",
        r"\bAT\b.*?\bDAM\b",
    )
]


@dataclass(frozen=True)
class RegulationHint:
    level: str    # likely_regulated | likely_unregulated | unknown
    reason: str


@dataclass(frozen=True)
class RegulatedGauge:
    site_no: str
    name: str
    regulator: str
    kind: str
    confidence: str
    source_url: str


def _validated(row: dict) -> RegulatedGauge:
    site = row["site_no"]
    if row["kind"] not in _KINDS:
        raise ValueError(f"regulated_gauges: site {site}: invalid kind {row['kind']!r}")
    if row["confidence"] not in _CONFIDENCES:
        raise ValueError(f"regulated_gauges: site {site}: invalid confidence {row['confidence']!r}")
    if not row["regulator"]:
        raise ValueError(f"regulated_gauges: site {site}: empty regulator")
    url = row["source_url"]
    if url and not _HTTP.match(url):
        # SPEC-GAP: contract only requires http(s) for high rows; a non-blank
        # non-http URL on a medium row is also rejected (most defensible).
        raise ValueError(f"regulated_gauges: site {site}: source_url is not http(s)")
    if row["confidence"] == "high" and not url:
        raise ValueError(f"regulated_gauges: site {site}: high confidence requires an http(s) source_url")
    return RegulatedGauge(**{c: row[c] for c in _COLUMNS})


@lru_cache(maxsize=None)
def regulated_gauges() -> dict[str, RegulatedGauge]:
    """Curated regulated gauges keyed by site_no (absence != unregulated)."""
    with open(_REGULATED_PATH, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in _COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"regulated_gauges: missing required column(s): {', '.join(missing)}")
        out: dict[str, RegulatedGauge] = {}
        for raw in reader:
            row = {c: (raw.get(c) or "").strip() for c in _COLUMNS}
            gauge = _validated(row)
            if gauge.site_no in out:
                raise ValueError(f"regulated_gauges: duplicate site_no {gauge.site_no}")
            out[gauge.site_no] = gauge
    return out


def _finite_area(area) -> float | None:
    try:
        value = float(area)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def regulation_hint(
    name: str | None, drainage_area_sqmi: float | None, site_no: str | None = None
) -> RegulationHint:
    """Classify a gage: regulated (curated) > likely_regulated (name) > likely_unregulated (size) > unknown."""
    known = regulated_gauges().get(site_no) if site_no else None
    if known:
        return RegulationHint(
            REGULATED,
            f"Known regulation: {known.regulator} ({known.kind}, {known.confidence} confidence; curated list).",
        )
    upper = (name or "").upper()
    for pattern in _REGULATED_PATTERNS:
        match = pattern.search(upper)
        if match:
            return RegulationHint(
                LIKELY_REGULATED,
                f"Station name contains '{match.group(0)}'. {_NOTE}",
            )
    area = _finite_area(drainage_area_sqmi)
    if area is not None and 0 < area < SMALL_BASIN_SQMI:
        return RegulationHint(
            LIKELY_UNREGULATED,
            f"Small drainage area ({area:g} mi2 < {SMALL_BASIN_SQMI:g}) and no "
            f"regulation keyword in the name. {_NOTE}",
        )
    return RegulationHint(UNKNOWN, f"No regulation keyword in the name and area is not small or unknown. {_NOTE}")
