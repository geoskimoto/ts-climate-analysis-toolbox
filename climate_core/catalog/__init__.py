"""Site catalogs: queryable USGS gage and SNOTEL station metadata."""

from climate_core.catalog.sites import Site, SiteCatalog, default_catalog
from climate_core.catalog.snotel import (
    SnotelCatalog,
    SnotelStation,
    default_snotel_catalog,
)

__all__ = [
    "Site",
    "SiteCatalog",
    "default_catalog",
    "SnotelStation",
    "SnotelCatalog",
    "default_snotel_catalog",
]
