"""Small shared helpers."""

import os
import re

import pandas as pd


def get_digits(text):
    """Return only the digits of a string (e.g. '12A' -> '12')."""
    return "".join(char for char in str(text) if char.isdigit())


def sanitize_filename(name):
    """Make a string safe to use as a file name."""
    sanitized = re.sub(r"[^\w\-]+", "_", str(name)).strip("_")
    return sanitized or "unnamed"


def ensure_directory(path):
    """Create *path* (and parents) if it does not exist yet."""
    if path:
        os.makedirs(path, exist_ok=True)
    return path


def parse_column_map(column_map_str):
    """Parse a CLI mapping string like 'Old=New,Alt=New2' into a dict.

    Returns an empty dict for None/empty input. Raises ValueError on
    malformed entries.
    """
    mapping = {}
    if not column_map_str:
        return mapping
    for entry in column_map_str.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(
                f"Invalid column mapping entry '{entry}' (expected 'OldName=NewName')"
            )
        old_name, new_name = entry.split("=", 1)
        mapping[old_name.strip()] = new_name.strip()
    return mapping


def normalize_columns(df, language=None, column_map=None):
    """Rename DataFrame columns to the canonical English names.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    language : str | None
        Name of a built-in alias preset from
        :data:`addrmap.constants.COLUMN_ALIASES` (e.g. 'german').
        Case-insensitive; None applies no preset.
    column_map : dict | None
        Custom mapping ``{old_name: new_name}`` applied on the raw
        headers. Takes precedence over the preset for the same old name.

    Returns
    -------
    pd.DataFrame
        DataFrame with renamed columns (copy if anything was renamed,
        otherwise the original object).
    """
    mapping = {}
    if column_map:
        mapping.update(column_map)

    if language:
        from .constants import COLUMN_ALIASES

        preset_key = language.lower()
        if preset_key not in COLUMN_ALIASES:
            known = ", ".join(sorted(COLUMN_ALIASES))
            raise ValueError(
                f"Unknown language preset '{language}'. Available: {known}"
            )
        for old_name, new_name in COLUMN_ALIASES[preset_key].items():
            mapping.setdefault(old_name, new_name)

    if mapping:
        df = df.rename(columns=mapping)
    return df


def validate_required_columns(df, required_columns, context="input"):
    """Raise a ValueError listing any missing columns."""
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required column(s) in {context}: {', '.join(missing)}. "
            f"Found: {', '.join(map(str, df.columns))}"
        )


def ensure_coordinate_columns(df):
    """Ensure Latitude/Longitude columns exist (as pd.NA) in a copy."""
    from .constants import COORDINATE_COLUMNS

    df = df.copy()
    for coordinate_column in COORDINATE_COLUMNS:
        if coordinate_column not in df.columns:
            df[coordinate_column] = pd.NA
        else:
            df[coordinate_column] = pd.to_numeric(
                df[coordinate_column], errors="coerce"
            )
    return df
