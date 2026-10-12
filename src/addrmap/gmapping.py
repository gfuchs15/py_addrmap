import os

import pandas as pd
import matplotlib.pyplot as plt

from gmplot import GoogleMapPlotter


def get_digits(text):
    return "".join(c for c in text if c.isdigit())


def generate_global_map_gmplot(df, api_key, output_file="map.html"):
    """
    Creates a global Google Map using gmplot with markers for all addresses.
    """

    # Center map on average coordinates
    avg_lat = df["Latitude"].mean()
    avg_lon = df["Longitude"].mean()

    gmap = GoogleMapPlotter(avg_lat, avg_lon, 15, apikey=api_key)

    # Ensure lat/lon columns
    if "Latitude" not in df.columns:
        df["Latitude"] = None
    if "Longitude" not in df.columns:
        df["Longitude"] = None

    # Add markers
    for _, row in df.iterrows():
        if pd.notna(row["Latitude"]) and pd.notna(row["Longitude"]):
            popup = f"{row['City']}<br>{row['Strasse']} {row['Nummer']}<br>{row['PLZ']}<br>{row['Name']}"
            gmap.marker(row["Latitude"], row["Longitude"], title=popup)

    gmap.draw(output_file)

    return df
