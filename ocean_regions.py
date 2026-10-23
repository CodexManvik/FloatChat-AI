"""
Named ocean regions used to label profiles and to understand region names in
user questions. Boxes are approximate and cover the Indian Ocean seed data.
"""

import re

# (name, keywords that refer to it in a question)
REGIONS = [
    ("Equatorial Indian Ocean", ["equator", "equatorial"]),
    ("Arabian Sea", ["arabian sea", "arabian"]),
    ("Bay of Bengal", ["bay of bengal", "bengal"]),
    ("Red Sea & Gulf of Aden", ["red sea", "gulf of aden"]),
    ("Southern Indian Ocean", ["southern indian", "south indian", "southern ocean"]),
    ("Eastern Indian Ocean", ["eastern indian", "east indian", "indonesia", "australia"]),
]

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]


def region_for(lat: float, lon: float) -> str:
    if -5 <= lat <= 5:
        return "Equatorial Indian Ocean"
    if lat > 10 and lon < 50:
        return "Red Sea & Gulf of Aden"
    if lat > 5 and lon < 78:
        return "Arabian Sea"
    if lat > 5 and lon < 100:
        return "Bay of Bengal"
    if lat < -5 and lon > 100:
        return "Eastern Indian Ocean"
    if lat < -5:
        return "Southern Indian Ocean"
    return "Eastern Indian Ocean"


def parse_filters(question: str) -> dict:
    """Extract region / month / year filters mentioned in a question."""
    q = question.lower()
    filters = {}
    for name, keywords in REGIONS:
        if any(k in q for k in keywords):
            filters["region"] = name
            break
    for i, month in enumerate(MONTHS, start=1):
        if re.search(rf"\b{month}\b|\b{month[:3]}\b", q):
            filters["month_num"] = i
            break
    if re.search(r"\b(oxygen|o2|bgc|biogeochemical)\b", q):
        filters["has_oxygen"] = True
    year = re.search(r"\b(20\d{2})\b", q)
    if year:
        filters["year"] = int(year.group(1))
    return filters
