"""Geocode addresses with Nominatim, with checkpointing and fallbacks.

Canonical column names: Street, Number, PostalCode, City, Name, Group,
Latitude, Longitude (see :mod:`addrmap.constants`).
"""

import os

import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from tqdm.auto import tqdm

from .constants import (
    CITY,
    LATITUDE,
    LONGITUDE,
    NAME,
    NUMBER,
    POSTAL_CODE,
    REQUIRED_ADDRESS_COLUMNS,
    STREET,
    DEFAULT_CHECKPOINT_FILE,
    DEFAULT_COUNTRY,
    DEFAULT_MIN_DELAY_S,
    DEFAULT_SAVE_EVERY,
    DEFAULT_USER_AGENT,
)
from .utils import (
    ensure_coordinate_columns,
    get_digits,
    validate_required_columns,
)


def build_address(street, number, postal_code, city, country=DEFAULT_COUNTRY):
    """Build a normalized free-form address string for geocoding.

    Missing parts are skipped gracefully.
    """
    parts = []
    if pd.notna(street) and str(street).strip():
        street_part = str(street).strip()
        if pd.notna(number) and str(number).strip():
            street_part = f"{street_part} {get_digits(str(number))}"
        parts.append(street_part)
    if pd.notna(postal_code) and str(postal_code).strip():
        parts.append(str(postal_code).strip())
    if pd.notna(city) and str(city).strip():
        parts.append(str(city).strip())
    if country and parts:
        parts.append(country)
    return ", ".join(parts)


def build_address_variants(street, number, postal_code, city, country=DEFAULT_COUNTRY):
    """Return progressively simpler address strings used as fallbacks."""
    primary = build_address(street, number, postal_code, city, country)
    if not primary:
        return []
    variants = [primary]
    without_country = build_address(street, number, postal_code, city, country=None)
    if without_country and without_country != primary:
        variants.append(without_country)
    postal_city = build_address(None, None, postal_code, city, country)
    if postal_city and postal_city not in variants:
        variants.append(postal_city)
    return variants


def save_geocoded_sorted(df, output_path, file_format=None, index=False):
    """Save geocoded rows (Latitude/Longitude populated) sorted by PostalCode.

    Parameters
    ----------

    df : pd.DataFrame
        Input data containing at least Latitude, Longitude and PostalCode columns.
    output_path : str
        Target file path.
    file_format : str | None, optional
        Output format: "csv" or "xlsx". If None, inferred from the extension.
    index : bool, optional
        Whether to write the DataFrame index.

    Returns
    -------
    pd.DataFrame
        Filtered and sorted DataFrame that has been saved.
    """
    from .constants import GROUP

    if file_format is None:
        _, extension = os.path.splitext(output_path)
        file_format = extension.lower().lstrip(".")
    if file_format not in ("csv", "xlsx"):
        raise ValueError("file_format must be 'csv' or 'xlsx'")

    required_cols = [LATITUDE, LONGITUDE, POSTAL_CODE]
    missing = [column for column in required_cols if column not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required column(s) for saving: {', '.join(missing)}"
        )

    result = df[df[LATITUDE].notna() & df[LONGITUDE].notna()].copy()

    keep_columns = [NAME, STREET, NUMBER, POSTAL_CODE, CITY]
    if GROUP in result.columns:
        keep_columns.append(GROUP)
    keep_columns = [column for column in keep_columns if column in result.columns]
    result = result[keep_columns]

    postal_numeric = pd.to_numeric(result[POSTAL_CODE], errors="coerce")
    result = (
        result.assign(**{"__postal_numeric": postal_numeric})
        .sort_values(
            ["__postal_numeric", POSTAL_CODE], ascending=True, na_position="last"
        )
        .drop(columns=["__postal_numeric"])
    )

    if file_format == "csv":
        result.to_csv(output_path, index=index)
    else:
        result.to_excel(output_path, index=index)

    return result


def load_checkpoint(path):
    """Load geocoding progress from a checkpoint CSV, or None if absent."""
    if not path or not os.path.exists(path):
        return None
    saved = pd.read_csv(path, index_col=0)
    print(f"Resumed from checkpoint {path}")
    return saved


def geocode_df(
    df,
    min_delay_s=DEFAULT_MIN_DELAY_S,
    user_agent=DEFAULT_USER_AGENT,
    country=DEFAULT_COUNTRY,
    output_csv=DEFAULT_CHECKPOINT_FILE,
    save_every=DEFAULT_SAVE_EVERY,
    resume_from_csv=False,
):
    """Geocode addresses in a DataFrame with fallbacks, progress bar and checkpointing.

    Missing or unparseable address data degrades gracefully: the geocoder
    tries progressively simpler address variants before giving up on a row.

    Parameters
    ----------

    df : pd.DataFrame
        Data with the canonical English column names (Street, Number,
        PostalCode, City, Name); Latitude/Longitude are created if absent.
    min_delay_s : float, optional
        Minimum delay between Nominatim requests (usage policy).
    user_agent : str, optional
        Identifying user agent for Nominatim.
    country : str | None, optional
        Country appended to every address (None omits it).
    output_csv : str | None, optional
        Checkpoint file for incremental saving and resume. None disables.
    save_every : int, optional
        Save the checkpoint every *save_every* successful geocodes.
    resume_from_csv : bool, optional
        Replace *df* with the checkpoint contents when the file exists.

    Returns
    -------
    pd.DataFrame
        DataFrame with filled Latitude/Longitude columns.
    """
    validate_required_columns(df, REQUIRED_ADDRESS_COLUMNS, context="input data")

    df = ensure_coordinate_columns(df)

    if resume_from_csv and output_csv:
        saved = load_checkpoint(output_csv)
        if saved is not None:
            df = ensure_coordinate_columns(saved)

    geolocator = Nominatim(user_agent=user_agent)
    print(f"Using user-agent: {user_agent}")

    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=min_delay_s,
        return_value_on_exception=None,
    )

    total = df.shape[0]
    print(f"📍 {total} rows, geocoding missing coordinates (rate-limited).")

    geocoded = 0
    failed = 0
    rows_since_save = 0

    for idx, row in tqdm(df.iterrows(), total=total):
        if pd.notna(row[LATITUDE]) and pd.notna(row[LONGITUDE]):
            continue

        address_variants = build_address_variants(
            street=row[STREET],
            number=row[NUMBER],
            postal_code=row[POSTAL_CODE],
            city=row[CITY],
            country=country,
        )

        location = None
        for address in address_variants:
            location = geocode(address)
            if location is not None:
                break

        if location is None:
            failed += 1
        else:
            df.at[idx, LATITUDE] = location.latitude
            df.at[idx, LONGITUDE] = location.longitude
            geocoded += 1
            rows_since_save += 1

        if output_csv and rows_since_save >= save_every:
            df.to_csv(output_csv)
            rows_since_save = 0
    print(f"✅ Geocoded: {geocoded} - ❌ Not found or blocked: {failed}")
    
    if output_csv:
        df.to_csv(output_csv)
        print(f"💾 Checkpoint saved to: {output_csv}")

    return df
