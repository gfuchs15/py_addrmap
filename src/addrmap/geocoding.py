from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from tqdm.auto import tqdm
import pandas as pd
import os


def get_digits(text):
    return "".join(c for c in text if c.isdigit())


def save_geocoded_sorted(df, output_path, file_format=None, index=False):
    """Save geocoded rows (Latitude/Longitude populated) sorted by PLZ.

    Parameters
    ----------
    df : pd.DataFrame
        Input data containing at least Latitude, Longitude, and PLZ columns.
    output_path : str
        Target file path.
    file_format : str | None, optional
        Output format: "csv" or "xlsx". If None, inferred from output_path extension.
    index : bool, optional
        Whether to write the DataFrame index.

    Returns
    -------
    pd.DataFrame
        Filtered and sorted DataFrame that has been saved.
    """
    required_cols = ["Latitude", "Longitude", "PLZ"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    result = df[df["Latitude"].notna() & df["Longitude"].notna()].copy()

    result = result[["Name", "Strasse", "Nummer", "PLZ", "City"]]

    # Numeric sort handles PLZ values stored as strings.
    plz_numeric = pd.to_numeric(result["PLZ"], errors="coerce")
    result = (
        result.assign(__plz_numeric=plz_numeric)
        .sort_values(["__plz_numeric", "PLZ"], ascending=True, na_position="last")
        .drop(columns=["__plz_numeric"])
    )

    if file_format is None:
        _, extension = os.path.splitext(output_path)
        file_format = extension.lower().lstrip(".")

    if file_format == "csv":
        result.to_csv(output_path, index=index)
    elif file_format == "xlsx":
        result.to_excel(output_path, index=index)
    else:
        raise ValueError("file_format must be 'csv' or 'xlsx'")

    return result


def geocode_df(
    df,
    min_delay_s=2,
    user_agent="guillaume_fuchs_geocode_df_2026",
    output_csv="geocoded_partial.csv",
    save_every=10,
):
    """Geocode addresses in a DataFrame with progress bar and checkpoint saving."""

    geolocator = Nominatim(user_agent=user_agent)
    print(f"Using user-agent: {user_agent}")

    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=min_delay_s,
        return_value_on_exception=None,
    )

    # Ensure Latitude and Longitude columns exist
    if "Latitude" not in df.columns:
        df["Latitude"] = pd.NA
    if "Longitude" not in df.columns:
        df["Longitude"] = pd.NA

    # ✅ Resume from CSV if it exists
    if os.path.exists(output_csv):
        df_saved = pd.read_csv(output_csv, index_col=0)
        # df.update(df_saved)
        df = df_saved
        print(f"Resumed from {output_csv}")

    total = df.shape[0]
    print(f"{total} addresses to geocode (rate‑limited).")

    geocoded = 0
    blocked = 0
    since_save = 0

    # ✅ Progress bar (Jupyter compatible)
    for idx, row in tqdm(df.iterrows(), total=total):
        if pd.notna(row["Latitude"]) and pd.notna(row["Longitude"]):
            continue

        num = (
            get_digits(row["Nummer"])
            if isinstance(row["Nummer"], str)
            else row["Nummer"]
        )
        address = f"{row['Strasse']} {num}, DE-{row['PLZ']} {row['City']}, Germany"

        location = geocode(address)

        if location is None:
            blocked += 1
        else:
            df.at[idx, "Latitude"] = location.latitude
            df.at[idx, "Longitude"] = location.longitude
            geocoded += 1
            since_save += 1

        # ✅ Incremental save
        if since_save >= save_every:
            df.to_csv(output_csv)
            since_save = 0

    # ✅ Final save
    df.to_csv(output_csv)

    print(f"✅ Geocoded: {geocoded}")
    print(f"❌ Blocked / not found: {blocked}")
    print(f"💾 Saved to: {output_csv}")

    return df


def geocode_df_v0(df, min_delay_s=2, user_agent="guillaume_fuchs_geocode_df_2026"):
    """geocode_df geocodes addresses in a DataFrame and adds Latitude and Longitude columns.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the addresses to be geocoded.
    min_delay_s : float, optional
        Minimum delay in seconds between geocoding requests to respect Nominatim's usage policy, by default 2

    Returns
    -------
    pd.DataFrame
        DataFrame with added Latitude and Longitude columns.
    """
    # Initialize geocoder with proper user-agent
    geolocator = Nominatim(user_agent)
    print(f"Using user-agent: {user_agent}")

    # Add strong rate limiting (2 seconds recommended)
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=min_delay_s,
        return_value_on_exception=None,
    )

    # Ensure Latitude and Longitude columns exist
    if "Latitude" not in df.columns:
        df["Latitude"] = None  # or np.nan, or any default value
    if "Longitude" not in df.columns:
        df["Longitude"] = None  # or np.nan, or any default value

    print(
        f"{df.shape[0]} addresses to geocode. This may take a while due to rate limiting."
    )
    geocoded = 0
    blocked = 0
    for idx, row in df.iterrows():
        if pd.notna(row["Latitude"]) and pd.notna(row["Longitude"]):
            continue

        num = (
            get_digits(row["Nummer"])
            if isinstance(row["Nummer"], str)
            else row["Nummer"]
        )
        address = f"{row['Strasse']} {num}, DE-{row['PLZ']} {row['City']}, Germany"
        location = geocode(address)
        if location is None:
            print("❌ Address not found or request blocked by Nominatim.")
            blocked += 1
        else:
            df.at[idx, "Latitude"] = location.latitude
            df.at[idx, "Longitude"] = location.longitude
            geocoded += 1

    print(f"✅ Geocoded: {geocoded} addresses.")
    print(f"❌ Blocked or not found: {blocked} addresses.")
    return df
