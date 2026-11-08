from pipeline.describe import describe_profile, value_at
from pipeline.shape import build_tables, to_seed
from tests.unit.test_shape import load_fixture_frames


def tables():
    return build_tables(to_seed(*load_fixture_frames()))


def profile_and_levels(float_id):
    _, profiles, measurements = tables()
    profile = profiles[profiles.float_id == float_id].iloc[0].to_dict()
    levels = measurements[measurements.float_id == float_id].sort_values("depth").reset_index(drop=True)
    return profile, levels


def test_value_at_tolerance():
    _, levels = profile_and_levels("2902203")
    assert value_at(levels, 200, "temperature") == levels.set_index("depth").loc[200.0, "temperature"]
    assert value_at(levels, 1500, "temperature") is None  # nothing within 15 % of 1,500 m


def test_description_of_bgc_profile():
    text = describe_profile(*profile_and_levels("2902203"))
    assert text.startswith("ARGO float 2902203 (WMO 2902203) profile cycle 45 on 11 February 2024")
    assert "12.30°N, 65.20°E in the Arabian Sea" in text
    assert "oxygen minimum" in text
    assert "chlorophyll maximum" in text
    assert "surface pH" in text
    assert "nitrate" not in text.lower()


def test_description_of_core_profile():
    text = describe_profile(*profile_and_levels("5905498"))
    assert "38.43°S" in text and "Eastern Indian Ocean" in text
    assert "oxygen" not in text
