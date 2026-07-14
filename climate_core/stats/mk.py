"""Helpers around the Mann-Kendall trend test.

``pymannkendall.original_test`` returns a namedtuple
``(trend, h, p, z, Tau, s, var_s, slope, intercept)``. ``mk_to_dict`` turns it
into a plain, JSON-serialisable dict -- the shape the web API will hand to the
frontend.
"""

from __future__ import annotations

from typing import Any


def mk_to_dict(result: Any) -> dict:
    """Convert a pymannkendall result namedtuple to a plain dict."""
    return {
        "trend": result.trend,          # 'increasing' | 'decreasing' | 'no trend'
        "significant": bool(result.h),  # True if the trend is significant at alpha
        "p_value": float(result.p),
        "z": float(result.z),
        "tau": float(result.Tau),
        "s": float(result.s),
        "var_s": float(result.var_s),
        "slope": float(result.slope),       # Sen's slope (units per year)
        "intercept": float(result.intercept),
    }
