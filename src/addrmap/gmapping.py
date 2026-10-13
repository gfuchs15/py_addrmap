"""Google Maps generation via gmplot (optional dependency).

Canonical column names: Street, Number, PostalCode, City, Name,
Latitude, Longitude (see :mod:`addrmap.constants`).
"""

import pandas as pd

from .constants import CITY, LATITUDE, LONGITUDE, NAME, NUMBER, POSTAL_CODE, STREET
from .utils import ensure_coordinate_columns


def generate_global_map_gmplot(df, api_key, output_file="map_google.html"):
    """Create a global Google Map using gmplot with markers for all addresses.

    Parameters
    ----------

    df : pd.DataFrame
        Data with canonical column names (Street, Number, PostalCode,
        City, Name, Latitude, Longitude).
    api_key : str
        Google Maps JavaScript API key.
    output_file : str, optional
        Path of the HTML map to write.

    Returns
    -------
    str | None
        Absolute path of the written map file, or None if skipped
        because gmplot is not installed.

    Raises
    ------
    ValueError
        If *api_key* is empty (the Google Maps API requires a key).
    """
    try:
        from gmplot import GoogleMapPlotter
    except ImportError:
        print(
            "⚠️ gmplot is not installed - skipping Google map. "
            "Install it with: pip install gmplot"
        )
        return None

    if not api_key:
        raise ValueError(
            "A Google Maps API key is required for the gmplot map "
            "(pass --api_key on the CLI)."
        )

    import os

    df = ensure_coordinate_columns(df)
    valid_rows = df[df[LATITUDE].notna() & df[LONGITUDE].notna()]
    if valid_rows.empty:
        raise ValueError(
            "No rows with valid coordinates: run geocode_df before mapping"
        )

    center_latitude = valid_rows[LATITUDE].mean()
    center_longitude = valid_rows[LONGITUDE].mean()

    gmap = GoogleMapPlotter(center_latitude, center_longitude, 15, apikey=api_key)

    for _, row in valid_rows.iterrows():
        popup = (
            f"{row[CITY]}<br>{row[STREET]} {row[NUMBER]}<br>"
            f"{row[POSTAL_CODE]}<br>{row[NAME]}"
        )
        gmap.marker(row[LATITUDE], row[LONGITUDE], title=popup)

    gmap.draw(output_file)
    print(f"✅ Google map saved to: {output_file}")
    return os.path.abspath(output_file)
