"""
Question filters (region, month, year, sensor) shared by profile search and the SQL templates.
Only these keys ever reach SQL, and values are always bound parameters.
"""

from floatchat.regions import REGIONS

REGION_NAMES = {name for name, _ in REGIONS}
SENSOR_KEYS = ("has_oxygen", "has_chlorophyll", "has_nitrate", "has_ph")
FILTER_KEYS = ("region", "month_num", "year") + SENSOR_KEYS

# {a} is the alias of the profiles table in the surrounding query
_CONDITIONS = {
    "region": "{a}.region = :region",
    "month_num": "EXTRACT(MONTH FROM {a}.profile_date) = :month_num",
    "year": "EXTRACT(YEAR FROM {a}.profile_date) = :year",
    **{key: "{a}." + key for key in SENSOR_KEYS},
}


def _as_int(value, low: int, high: int):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def clean_filters(filters: dict | None) -> dict:
    """Keep only known keys with valid values (an LLM or a client may send anything)."""
    clean = {}
    for key, value in (filters or {}).items():
        if key == "region" and value in REGION_NAMES:
            clean[key] = value
        elif key == "month_num" and (month := _as_int(value, 1, 12)) is not None:
            clean[key] = month
        elif key == "year" and (year := _as_int(value, 2000, 2100)) is not None:
            clean[key] = year
        elif key in SENSOR_KEYS and value is True:
            clean[key] = True
    return clean


def sql_conditions(filters: dict, alias: str) -> tuple[list[str], dict]:
    """SQL conditions and bound parameters for already-clean filters."""
    conditions = [_CONDITIONS[key].format(a=alias) for key in FILTER_KEYS if key in filters]
    params = {key: filters[key] for key in ("region", "month_num", "year") if key in filters}
    return conditions, params
