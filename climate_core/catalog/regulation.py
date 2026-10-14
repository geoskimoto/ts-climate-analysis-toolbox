"""Name/size heuristic for flow regulation of a USGS gage.

This is a screening hint only: it looks at the station name and the drainage
area and is NOT a verified determination of regulation.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

LIKELY_REGULATED = "likely_regulated"
LIKELY_UNREGULATED = "likely_unregulated"
UNKNOWN = "unknown"

SMALL_BASIN_SQMI = 200.0   # below this (and > 0) the basin is "likely unregulated"

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


def _finite_area(area) -> float | None:
    try:
        value = float(area)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def regulation_hint(name: str | None, drainage_area_sqmi: float | None) -> RegulationHint:
    """Classify a gage as likely regulated / unregulated / unknown."""
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
