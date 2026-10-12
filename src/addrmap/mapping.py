"""Folium map generation.

Canonical column names: Street, Number, PostalCode, City, Name, Group,
Latitude, Longitude (see :mod:`addrmap.constants`).
"""

import os

import matplotlib

# This module only renders figures to PNG files (fig.savefig); it never opens
# an interactive window, so pin the non-interactive Agg backend. Without this,
# matplotlib may pick TkAgg and fail on systems without a usable Tcl/Tk.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import folium
from folium.plugins import LocateControl

from .constants import (
    CITY,
    GROUP,
    LATITUDE,
    LONGITUDE,
    NAME,
    NUMBER,
    POSTAL_CODE,
    STREET,
    DEFAULT_MAP_TYPE,
)
from .utils import ensure_directory, get_digits, sanitize_filename  # noqa: F401 (get_digits re-exported for backwards compatibility)

# ----------------------------------------------------------
# MAP TILE PROFILES (URLs + Info)
# ----------------------------------------------------------

TILES = {
    "osm": {
        "url": "OpenStreetMap",
        "attr": "© OpenStreetMap contributors",
        "description": "OpenStreetMap tiles, good for Germany, more detailed than standard OSM.",
        "pros": ["More detailed in Germany", "Good street names", "Free and open"],
        "cons": [
            "May return HTTP 403 when the map is opened via file:// (no Referer)",
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

MARKER_COLORS = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "darkred",
    "cadetblue",
    "darkgreen",
    "pink",
    "lightblue",
]

DEFAULT_MARKER_ZOOM = 15
DEFAULT_GROUP_ZOOM = 14


def _resolve_tiles(map_type):
    """Return the tile profile for map_type; raise ValueError if unknown."""
    if map_type not in TILES:
        known = ", ".join(sorted(TILES))
        raise ValueError(f"Unknown map_type '{map_type}'. Available: {known}")
    return TILES[map_type]


def _build_marker_popup(row):
    """Build the HTML popup text for one address row.

    Tolerates missing optional columns.
    """
    lines = []
    if NAME in row.index and pd.notna(row[NAME]):
        lines.append(f"<b>{row[NAME]}</b>")
    if STREET in row.index and pd.notna(row[STREET]):
        street_line = str(row[STREET])
        if NUMBER in row.index and pd.notna(row[NUMBER]):
            street_line = f"{street_line} {row[NUMBER]}"
        lines.append(street_line)
    city_parts = []
    if POSTAL_CODE in row.index and pd.notna(row[POSTAL_CODE]):
        city_parts.append(str(row[POSTAL_CODE]))
    if CITY in row.index and pd.notna(row[CITY]):
        city_parts.append(str(row[CITY]))
    if city_parts:
        lines.append(" ".join(city_parts))
    return "<br>".join(lines)


def _marker_rows(df):
    """Yield (index, row) for rows with valid coordinates."""
    for idx, row in df.iterrows():
        if pd.notna(row[LATITUDE]) and pd.notna(row[LONGITUDE]):
            yield idx, row


def _validate_map_input(df):
    """Ensure the coordinate columns needed for mapping exist."""
    from .utils import ensure_coordinate_columns

    return ensure_coordinate_columns(df)


def add_markers(map_obj, df, color=None, tooltip_column=NAME):
    """Add one Folium marker per row with valid coordinates.

    Parameters
    ----------

    map_obj : folium.Map
        Map to add markers to.
    df : pd.DataFrame
        Rows with canonical column names.
    color : str | None, optional
        Marker color; None uses Folium's default color.
    tooltip_column : str, optional
        Column whose value is shown as marker tooltip.
    """
    for _, row in _marker_rows(df):
        marker_kwargs = {
            "location": [row[LATITUDE], row[LONGITUDE]],
            "popup": _build_marker_popup(row),
        }
        tooltip = (
            row[tooltip_column]
            if tooltip_column in df.columns and pd.notna(row[tooltip_column])
            else None
        )
        if tooltip is not None:
            marker_kwargs["tooltip"] = str(tooltip)
        if color is not None:
            marker_kwargs["icon"] = folium.Icon(color=color)
        folium.Marker(**marker_kwargs).add_to(map_obj)


def generate_global_map(
    df, output_file="map.html", map_type=DEFAULT_MAP_TYPE, zoom_start=DEFAULT_MARKER_ZOOM
):
    """Create a single global map with one marker per address.

    Parameters
    ----------

    df : pd.DataFrame
        Data with canonical column names (Street, Number, PostalCode,
        City, Name, Latitude, Longitude).
    output_file : str, optional
        Path of the HTML map to write.
    map_type : str, optional
        Tile profile key from :data:`TILES`.
    zoom_start : int, optional
        Initial zoom level.

    Returns
    -------
    str
        Absolute path of the written map file.
    """
    if df.empty:
        raise ValueError("Cannot generate a map from an empty DataFrame")

    tile_profile = _resolve_tiles(map_type)
    df = _validate_map_input(df)

    output_dir = os.path.dirname(os.path.abspath(output_file))
    ensure_directory(output_dir)

    valid_rows = df[df[LATITUDE].notna() & df[LONGITUDE].notna()]
    if valid_rows.empty:
        raise ValueError(
            "No rows with valid coordinates: run geocode_df before mapping"
        )

    center_latitude = valid_rows[LATITUDE].mean()
    center_longitude = valid_rows[LONGITUDE].mean()

    map_obj = folium.Map(
        location=[center_latitude, center_longitude],
        zoom_start=zoom_start,
        tiles=tile_profile["url"],
        attr=tile_profile["attr"],
    )

    add_markers(map_obj, valid_rows)

    map_obj.save(output_file)
    print(f"[OK] Map saved to: {output_file}")
    return os.path.abspath(output_file)


def generate_group_map(
    df,
    filter_col=GROUP,
    output_file="map_groups.html",
    map_type=DEFAULT_MAP_TYPE,
    zoom_start=DEFAULT_GROUP_ZOOM,
):
    """Create one map with a colored, toggleable feature group per group.

    Parameters
    ----------

    df : pd.DataFrame
        Data with canonical column names.
    filter_col : str, optional
        Column used to group addresses (e.g. Group).
    output_file : str, optional
        Path of the HTML map to write.
    map_type : str, optional
        Tile profile key from :data:`TILES`.
    zoom_start : int, optional
        Initial zoom level.

    Returns
    -------
    str
        Absolute path of the written map file.
    """
    if filter_col not in df.columns:
        raise ValueError(f"Group column '{filter_col}' not found in data")

    tile_profile = _resolve_tiles(map_type)
    df = _validate_map_input(df)

    output_dir = os.path.dirname(os.path.abspath(output_file))
    ensure_directory(output_dir)

    valid_rows = df[df[LATITUDE].notna() & df[LONGITUDE].notna()]
    if valid_rows.empty:
        raise ValueError(
            "No rows with valid coordinates: run geocode_df before mapping"
        )

    first = valid_rows.iloc[0]

    map_obj = folium.Map(
        location=[first[LATITUDE], first[LONGITUDE]],
        zoom_start=zoom_start,
        tiles=tile_profile["url"],
        attr=tile_profile["attr"],
    )

    LocateControl(auto_start=False).add_to(map_obj)

    for group_index, (group_name, group_df) in enumerate(
        valid_rows.groupby(filter_col)
    ):
        color = MARKER_COLORS[group_index % len(MARKER_COLORS)]
        feature_group = folium.FeatureGroup(
            name=f"<span style='color:{color};'>● {group_name}</span>",
            show=True,
        )
        add_markers(feature_group, group_df, color=color)
        feature_group.add_to(map_obj)

    folium.LayerControl(collapsed=True).add_to(map_obj)

    map_obj.save(output_file)
    print(f"[OK] Map saved to: {output_file}")
    return os.path.abspath(output_file)


def generate_filter_maps(
    df, filter_col=GROUP, output_dir="out", map_type=DEFAULT_MAP_TYPE
):
    """Create one map (and one PNG address table) per group.

    Parameters
    ----------

    df : pd.DataFrame
        Data with canonical column names.
    filter_col : str, optional
        Column used to group addresses (e.g. Group).
    output_dir : str, optional
        Directory to write the per-group maps and PNG tables into.
    map_type : str, optional
        Tile profile key from :data:`TILES`.

    Returns
    -------
    dict
        Mapping ``{group_name: {"html": path, "png": path}}``.
    """
    if filter_col not in df.columns:
        raise ValueError(f"Filter column '{filter_col}' not found in data")

    tile_profile = _resolve_tiles(map_type)
    df = _validate_map_input(df)
    ensure_directory(output_dir)

    written_files = {}

    for group_name, group_df in df.groupby(filter_col):
        if group_df.empty:
            continue

        table_data = group_df[[STREET, NUMBER, NAME]].dropna(subset=[NAME])
        fig, ax = plt.subplots(figsize=(8, len(group_df) * 0.4))
        ax.axis("tight")
        ax.axis("off")
        ax.set_title(f"{group_name} - {len(table_data)} addresses")
        table = ax.table(
            cellText=table_data.values,
            colLabels=table_data.columns,
            cellLoc="center",
            loc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.2)

        png_path = os.path.join(
            output_dir, f"locations_list_{sanitize_filename(group_name)}.png"
        )
        fig.savefig(png_path, bbox_inches="tight")
        plt.close(fig)

        valid_rows = group_df[
            group_df[LATITUDE].notna() & group_df[LONGITUDE].notna()
        ]
        if valid_rows.empty:
            print(f"[WARN] No valid coordinates for group '{group_name}', map skipped")
            continue

        first_location = valid_rows.iloc[0]
        map_obj = folium.Map(
            location=[first_location[LATITUDE], first_location[LONGITUDE]],
            zoom_start=16,
            tiles=tile_profile["url"],
            attr=tile_profile["attr"],
        )
        add_markers(map_obj, valid_rows)

        html_path = os.path.join(
            output_dir, f"map_{sanitize_filename(group_name)}.html"
        )
        map_obj.save(html_path)

        written_files[group_name] = {"html": html_path, "png": png_path}

    return written_files
