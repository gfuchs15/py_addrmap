import os

import pandas as pd
import matplotlib.pyplot as plt

import folium


# ----------------------------------------------------------
# 1. MAP TILE PROFILES (URLs + Info)
# ----------------------------------------------------------

TILES = {
    "osm": {
        "url": "OpenStreetMap",
        "attr": "© OpenStreetMap contributors",
        "description": "OpenStreetMap tiles, good for Germany, more detailed than standard OSM.",
        "pros": ["More detailed in Germany", "Good street names", "Free and open"],
        "cons": [
            "Slightly slower than standard OSM",
            "House numbers not always complete",
        ],
    },
    "esri_street": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "attr": "Tiles © Esri — Source: Esri, DeLorme, NAVTEQ",
        "description": "Professional map similar to Google Maps, high detail, very stable.",
        "pros": ["Highly stable", "Good detail and street names", "Fast loading"],
        "cons": ["House numbers not always complete", "Slightly more colorful"],
    },
    "carto": {
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "attr": "© OpenStreetMap contributors © CARTO",
        "description": "Very light and minimalistic map, popular for data visualization.",
        "pros": ["Very clean design", "Fast"],
        "cons": ["Few details", "House numbers missing"],
    },
}


def get_digits(text):
    return "".join(c for c in text if c.isdigit())


def generate_global_map(df, output_file="map.html", map_type="esri_street"):
    """generate_main_map geocodes addresses in a DataFrame and creates a global map with markers.
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the addresses to be geocoded.
    initial_address : str, optional
        Initial address to center the map, by default "Eichenplatz 1, 91088 Bubenreuth, Germany"
    Returns
    -------
    """
    tile_cfg = TILES[map_type]

    avg_lat = df["Latitude"].mean()
    avg_lon = df["Longitude"].mean()

    m = folium.Map(
        location=[avg_lat, avg_lon],
        zoom_start=15,
        tiles=tile_cfg["url"],
        attr=tile_cfg["attr"],
    )

    # Ensure Latitude and Longitude columns exist
    if "Latitude" not in df.columns:
        df["Latitude"] = None  # or np.nan, or any default value
    if "Longitude" not in df.columns:
        df["Longitude"] = None  # or np.nan, or any default value

    for idx, row in df.iterrows():
        if pd.notna(row["Latitude"]) and pd.notna(row["Longitude"]):
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=f"{row['City']}<br>{row['Strasse']} {row['Nummer']}<br>{row['PLZ']}<br>{row['Name']}",
            ).add_to(m)

    m.save(output_file)

    return df


def generate_filter_maps(
    df, filter_col="Viertel", output_dir="./out", map_type="esri_street"
):
    for quarter, group in df.groupby(filter_col):
        if group.empty:
            continue

        fig, ax = plt.subplots(figsize=(8, len(group) * 0.4))
        ax.axis("tight")
        ax.axis("off")

        table_data = group[["Strasse", "Nummer", "Name"]]
        ax.set_title(f"{quarter} - {len(table_data)} Adressen")

        table = ax.table(
            cellText=table_data.values,
            colLabels=table_data.columns,
            cellLoc="center",
            loc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.2)

        fig.savefig(
            os.path.join(output_dir, f"locations_list_{quarter}.png"),
            bbox_inches="tight",
        )
        plt.close()

        first_location = group.iloc[0]

        if pd.notna(first_location["Latitude"]):
            m = folium.Map(
                location=[first_location["Latitude"], first_location["Longitude"]],
                zoom_start=16,
                tiles=TILES[map_type]["url"],
                attr=TILES[map_type]["attr"],
                user_agent="addrmap_gfuchs_v0.2",
            )

            for _, row in group.iterrows():
                if pd.notna(row["Latitude"]) and pd.notna(row["Longitude"]):
                    # Create a FeatureGroup with a unique name
                    fg = folium.FeatureGroup(name=f"{row['Name']}")

                    folium.Marker(
                        location=[row["Latitude"], row["Longitude"]],
                        popup=(
                            f"<b>{row['Name']}</b><br>"
                            f"{row['Strasse']} {row['Nummer']}<br>"
                            f"{row['PLZ']} {row['City']}"
                        ),
                        tooltip=row["Name"],
                    ).add_to(fg)
                    fg.add_to(m)

            # Add layer control for checkboxes
            folium.LayerControl(collapsed=False).add_to(m)

            filepath = os.path.join(output_dir, f"map_{quarter}.html")
            m.save(filepath)
