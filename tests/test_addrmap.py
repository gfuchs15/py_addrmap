import os

import pandas as pd
import pytest

from addrmap.constants import (
    CITY,
    GROUP,
    LATITUDE,
    LONGITUDE,
    NAME,
    NUMBER,
    POSTAL_CODE,
    STREET,
)
from addrmap.geocoding import build_address, build_address_variants, geocode_df
from addrmap.main import parse_arguments, run_pipeline
from addrmap.mapping import generate_filter_maps, generate_global_map, generate_group_map
from addrmap.utils import get_digits, normalize_columns, parse_column_map, sanitize_filename


def test_get_digits():
    assert get_digits("12A") == "12"
    assert get_digits("B34") == "34"
    assert get_digits("No number") == ""


def test_sanitize_filename():
    assert sanitize_filename("Prenzlauer Berg") == "Prenzlauer_Berg"
    assert sanitize_filename("") == "unnamed"


def test_parse_column_map():
    assert parse_column_map(None) == {}
    assert parse_column_map("") == {}
    assert parse_column_map("a=b, c = d ") == {"a": "b", "c": "d"}
    with pytest.raises(ValueError):
        parse_column_map("invalid_entry")


def test_normalize_columns_german_preset():
    df = pd.DataFrame(
        columns=["Strasse", "Nummer", "PLZ", "City", "Name", "Viertel"]
    )
    normalized = normalize_columns(df, language="german")
    assert list(normalized.columns) == [
        STREET,
        NUMBER,
        POSTAL_CODE,
        CITY,
        NAME,
        GROUP,
    ]


def test_normalize_columns_custom_map_wins():
    df = pd.DataFrame(columns=["Quartier", "Name"])
    normalized = normalize_columns(
        df, language="german", column_map={"Quartier": GROUP}
    )
    assert list(normalized.columns) == [GROUP, NAME]


def test_normalize_columns_unknown_language():
    df = pd.DataFrame(columns=["Strasse"])
    with pytest.raises(ValueError):
        normalize_columns(df, language="klingon")


def test_build_address():
    address = build_address(
        street="Invalidenstr.", number="12A", postal_code="10115", city="Berlin"
    )
    assert address == "Invalidenstr. 12, 10115, Berlin, Germany"


def test_build_address_variants():
    variants = build_address_variants(
        street="Invalidenstr.", number="12A", postal_code="10115", city="Berlin"
    )
    assert variants[0] == "Invalidenstr. 12, 10115, Berlin, Germany"
    assert "Invalidenstr. 12, 10115, Berlin" in variants
    assert variants[-1] == "10115, Berlin, Germany"


def test_build_address_missing_parts():
    assert build_address(street=None, number=None, postal_code=None, city=None) == ""
    assert (
        build_address(street=None, number=None, postal_code=None, city="Berlin")
        == "Berlin, Germany"
    )


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            GROUP: ["Mitte", "Mitte", "Kreuzberg"],
            STREET: ["Invalidenstr.", "Kollwitzstr.", "Oranienstr."],
            NUMBER: ["12A", "7", "45B"],
            POSTAL_CODE: ["10115", "10405", "10997"],
            CITY: ["Berlin"] * 3,
            NAME: ["Schmidt, Anna", "Keller, Tom", "Hassan, Leila"],
            LATITUDE: [52.53, 52.54, 52.50],
            LONGITUDE: [13.39, 13.42, 13.41],
        }
    )


def test_generate_global_map(tmp_path, sample_df):
    output_file = tmp_path / "map.html"
    result = generate_global_map(
        sample_df, output_file=str(output_file), map_type="esri_street"
    )
    assert os.path.exists(result)
    content = output_file.read_text(encoding="utf-8")
    assert "Schmidt, Anna" in content
    assert "Oranienstr." in content


def test_generate_global_map_requires_coordinates(tmp_path):
    df = pd.DataFrame(
        {STREET: ["x"], NUMBER: ["1"], POSTAL_CODE: ["1"], CITY: ["y"], NAME: ["z"]}
    )
    with pytest.raises(ValueError):
        generate_global_map(df, output_file=str(tmp_path / "map.html"))


def test_generate_global_map_unknown_map_type(tmp_path, sample_df):
    with pytest.raises(ValueError):
        generate_global_map(sample_df, output_file=str(tmp_path / "map.html"), map_type="nope")


def test_generate_group_map(tmp_path, sample_df):
    output_file = tmp_path / "map_groups.html"
    result = generate_group_map(sample_df, output_file=str(output_file))
    assert os.path.exists(result)
    content = output_file.read_text(encoding="utf-8")
    assert "Mitte" in content


def test_generate_group_map_missing_column(tmp_path, sample_df):
    with pytest.raises(ValueError):
        generate_group_map(sample_df, filter_col="Nope", output_file=str(tmp_path / "m.html"))


def test_generate_filter_maps(tmp_path, sample_df):
    written = generate_filter_maps(
        sample_df, filter_col=GROUP, output_dir=str(tmp_path / "groups")
    )
    assert set(written) == {"Mitte", "Kreuzberg"}
    for entry in written.values():
        assert os.path.exists(entry["html"])
        assert os.path.exists(entry["png"])
    assert "Prenzlauer" not in os.listdir(tmp_path / "groups")
    # Spaces in group names must be sanitized in file names
    sample_df[GROUP] = ["Mitte West", "Mitte West", "Kreuzberg"]
    written = generate_filter_maps(
        sample_df, filter_col=GROUP, output_dir=str(tmp_path / "groups2")
    )
    assert os.path.exists(tmp_path / "groups2" / "map_Mitte_West.html")


def test_generate_filter_maps_skips_group_without_coordinates(tmp_path):
    df = pd.DataFrame(
        {
            GROUP: ["A", "B"],
            STREET: ["x", "y"],
            NUMBER: ["1", "2"],
            NAME: ["n1", "n2"],
            LATITUDE: [52.0, None],
            LONGITUDE: [13.0, None],
        }
    )
    written = generate_filter_maps(df, filter_col=GROUP, output_dir=str(tmp_path / "g"))
    assert set(written) == {"A"}


def test_geocode_df_missing_required_columns():
    with pytest.raises(ValueError):
        geocode_df(pd.DataFrame(columns=[STREET]), output_csv=None)


def test_run_pipeline_renames_german_columns_and_generates_maps(tmp_path):
    input_path = os.path.join(os.path.dirname(__file__), "smoke_input.csv")
    args = parse_arguments(
        ["-i", input_path, "-o", str(tmp_path / "out"), "--skip_geocode"]
    )
    result = run_pipeline(args)
    out_dir = tmp_path / "out"
    for expected in (
        "enriched_addresses.xlsx",
        "map.html",
        "map_groups.html",
        "map_Mitte.html",
        "locations_list_Mitte.png",
    ):
        assert (out_dir / expected).exists(), f"missing {expected}"
    html = (out_dir / "map_groups.html").read_text(encoding="utf-8")
    assert "Mitte" in html
    assert result is None or result
