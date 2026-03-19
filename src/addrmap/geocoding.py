import pandas as pd

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


def get_digits(text):
    return "".join(c for c in text if c.isdigit())


def geocode_df(df, min_delay_s=2):
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
    geolocator = Nominatim(user_agent="guillaume_fuchs_geocoder_test_2026")

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
