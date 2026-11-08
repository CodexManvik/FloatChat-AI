import pytest

from floatchat.regions import parse_filters, region_for


@pytest.mark.parametrize("lat,lon,expected", [
    (0.5, 70, "Equatorial Indian Ocean"),
    (15, 65, "Arabian Sea"),
    (15, 88, "Bay of Bengal"),
    (13, 45, "Red Sea & Gulf of Aden"),
    (-30, 60, "Southern Indian Ocean"),
    (-20, 110, "Eastern Indian Ocean"),
])
def test_region_for(lat, lon, expected):
    assert region_for(lat, lon) == expected


def test_parse_filters_region_month_year():
    assert parse_filters("salinity profiles near the equator in March 2024") == {
        "region": "Equatorial Indian Ocean", "month_num": 3, "year": 2024}


def test_parse_filters_sensors():
    assert parse_filters("low oxygen in the Arabian Sea") == {"region": "Arabian Sea", "has_oxygen": True}
    assert parse_filters("where is chlorophyll highest?") == {"has_chlorophyll": True}
    assert parse_filters("nitrate and pH in the Bay of Bengal") == {
        "region": "Bay of Bengal", "has_nitrate": True, "has_ph": True}


def test_parse_filters_nothing():
    assert parse_filters("tell me about floats") == {}
