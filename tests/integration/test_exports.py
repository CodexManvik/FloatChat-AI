import pytest

from floatchat.exports import EXPORTERS

pytestmark = pytest.mark.integration


def test_csv_includes_bgc_columns(reader_engine):
    content = EXPORTERS["csv"][0](reader_engine, [], [1, 2])
    header = content.splitlines()[0]
    assert header.startswith("float_id,profile_id,time") and "chlorophyll" in header


def test_netcdf_is_hdf5(reader_engine):
    content = EXPORTERS["netcdf"][0](reader_engine, [], [1])
    assert content[:4] == b"\x89HDF"


def test_ascii_header(reader_engine):
    content = EXPORTERS["ascii"][0](reader_engine, [], [1])
    assert content.startswith("# ARGO Float Data Export") and "# Number of profiles: 1" in content
