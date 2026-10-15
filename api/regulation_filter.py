"""Regulation fields and filtering for the site-list routes."""

from __future__ import annotations

from api import schemas
from climate_core.catalog import Site
from climate_core.catalog.regulation import REGULATION_LEVELS, regulation_hint


def parse_levels(raw: str | None) -> set[str] | None:
    """Parse a comma-separated ``regulation`` query value.

    Returns None for no filter (absent, empty, or only commas/whitespace).
    Level names are case-sensitive; unknown names raise ``ValueError`` naming them.
    """
    items = [i.strip() for i in (raw or "").split(",") if i.strip()]
    if not items:
        return None
    bad = [i for i in dict.fromkeys(items) if i not in REGULATION_LEVELS]
    if bad:
        raise ValueError(
            f"Unknown regulation level(s): {', '.join(bad)}. Valid: {', '.join(REGULATION_LEVELS)}."
        )
    return set(items)


def with_regulation(site: Site) -> schemas.SiteWithRegulation:
    hint = regulation_hint(site.name, site.drainage_area_sqmi, site_no=site.site_no)
    return schemas.SiteWithRegulation(
        **site.to_dict(), regulation_level=hint.level, regulation_reason=hint.reason
    )


def filter_sites(sites: list[Site], levels: set[str] | None, limit: int) -> list[schemas.SiteWithRegulation]:
    """Annotate ``sites`` and keep those whose level is in ``levels`` (before ``limit``)."""
    out = []
    for site in sites:
        item = with_regulation(site)
        if levels is None or item.regulation_level in levels:
            out.append(item)
            if len(out) >= limit:
                break
    return out
