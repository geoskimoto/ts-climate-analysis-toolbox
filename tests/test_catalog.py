"""Site catalog tests."""

import pytest

from climate_core.catalog import SiteCatalog, default_catalog


@pytest.fixture(scope="module")
def catalog():
    return default_catalog()


def test_catalog_loads(catalog):
    assert len(catalog) > 800


def test_every_site_is_geocoded(catalog):
    for site in catalog.all():
        assert site.lat is not None and site.long is not None
        # PNW bounding box sanity check.
        assert 40 <= site.lat <= 55
        assert -125 <= site.long <= -108


def test_get_known_site(catalog):
    # Clearwater R at Orofino -- one of the original "vip_sites".
    site = catalog.get("13340000")
    assert "CLEARWATER" in site.name.upper()
    assert site.state == "ID"


def test_get_missing_site_raises(catalog):
    with pytest.raises(KeyError):
        catalog.get("00000000")


def test_search_by_state_and_text(catalog):
    wa = catalog.search(state="WA")
    assert wa and all(s.state == "WA" for s in wa)
    salmon = catalog.search(query="salmon")
    assert all("SALMON" in s.name.upper() for s in salmon)


def test_site_to_dict_roundtrip(catalog):
    d = catalog.get("13340000").to_dict()
    assert set(d) >= {"site_no", "name", "lat", "long", "state"}
