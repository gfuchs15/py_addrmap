"""Folium map generation.

Canonical column names: Street, Number, PostalCode, City, Name, Group,
Latitude, Longitude (see :mod:`addrmap.constants`).
"""

import html
import os
import re

import matplotlib

matplotlib.use("Agg")  # render PNG tables without a display server

import matplotlib.pyplot as plt
import pandas as pd
import folium
from branca.element import Element
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
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png?key=cb1_4ihm_1_65fd5d1428bcb0e8cc3a88e3",
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
DEFAULT_LIST_ZOOM = 17

# Approximate CSS colors for the Leaflet marker palette (used for the dots in
# the address list so entries visually match their markers).
_MARKER_HEX = {
    "red": "#d9534f",
    "blue": "#337ab7",
    "green": "#5cb85c",
    "purple": "#9b59b6",
    "orange": "#f0ad4e",
    "darkred": "#a93226",
    "cadetblue": "#5f9ea0",
    "darkgreen": "#1e7a1e",
    "pink": "#ff9eb5",
    "lightblue": "#77a4ce",
}
_DEFAULT_DOT_COLOR = "#337ab7"
#: Color used for markers and checkbox accents of visited addresses.
_VISITED_COLOR = "#2ca02c"


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


def _house_number_key(text):
    """Sort key ordering house numbers naturally ("2" < "10" < "10a")."""
    return [
        (int(part), "") if part.isdigit() else (0, part.lower())
        for part in re.split(r"(\d+)", text)
    ]


def _sorted_marker_rows(df):
    """Yield rows sorted by street, then natural house number, then name."""
    def address_key(row):
        return (
            _cell_text(row, STREET).lower(),
            _house_number_key(_cell_text(row, NUMBER)),
            _cell_text(row, NAME).lower(),
        )

    return sorted(_marker_rows(df), key=lambda pair: address_key(pair[1]))


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


_ADDRESS_LIST_CSS = """
#addrmap-list{position:fixed;top:12px;right:12px;width:320px;max-width:calc(100vw - 24px);
max-height:calc(100vh - 24px);z-index:1100;display:flex;flex-direction:column;
background:rgba(255,255,255,.97);border:1px solid rgba(0,0,0,.08);border-radius:10px;
box-shadow:0 6px 24px rgba(0,0,0,.25);overflow:hidden;
font-family:system-ui,'Segoe UI',Roboto,Arial,sans-serif;color:#222}
#addrmap-list *{box-sizing:border-box}
#addrmap-list .addrmap-header{display:flex;align-items:center;justify-content:flex-end;padding:8px 12px;border-bottom:1px solid #eee}
#addrmap-list .addrmap-toggle{padding:6px 10px;font-size:14px;line-height:1;border:none;border-radius:6px;background:#f0f2f5;color:#555;cursor:pointer}
#addrmap-list .addrmap-toggle:hover{background:#e2e6ea}
#addrmap-list .addrmap-title{padding:8px 12px;font-size:13px;font-weight:600;border-bottom:1px solid #eee}
#addrmap-list .addrmap-items{list-style:none;margin:0;padding:0;overflow-y:auto;flex:1}
#addrmap-list .addrmap-item{display:flex;align-items:flex-start;gap:10px;padding:8px 12px}
#addrmap-list .addrmap-check{flex:0 0 auto;margin:2px 4px 0 0;cursor:pointer;accent-color:__VISITED_COLOR__}
#addrmap-list .addrmap-dot{flex:0 0 auto;width:10px;height:10px;margin-top:5px;border-radius:50%}
#addrmap-list .addrmap-entry{display:flex;flex-direction:column;gap:1px;min-width:0;cursor:pointer}
#addrmap-list .addrmap-item:hover .addrmap-entry{background:#f0f4f8}
#addrmap-list .addrmap-name{font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#addrmap-list .addrmap-street,#addrmap-list .addrmap-city{font-size:12px;color:#666}
#addrmap-list .addrmap-group{font-size:11px;color:#999}
#addrmap-list .addrmap-item.addrmap-visited .addrmap-name{text-decoration:line-through;color:#999}
#addrmap-list .addrmap-item.addrmap-visited .addrmap-street,
#addrmap-list .addrmap-item.addrmap-visited .addrmap-city,
#addrmap-list .addrmap-item.addrmap-visited .addrmap-group{color:#aaa}
#addrmap-list .addrmap-item.addrmap-visited .addrmap-dot{background:__VISITED_COLOR__ !important}
#addrmap-list.addrmap-collapsed .addrmap-title,#addrmap-list.addrmap-collapsed .addrmap-items{display:none}
#addrmap-list.addrmap-collapsed{width:auto;max-width:none}
@media (max-width:640px){#addrmap-list{width:calc(100vw - 24px)}}
@media print{
#addrmap-list{position:static;width:100%;max-width:none;max-height:none;border:none;box-shadow:none;background:none;border-radius:0}
#addrmap-list .addrmap-toggle{display:none}
#addrmap-list .addrmap-items{overflow:visible}
#addrmap-list .addrmap-item{break-inside:avoid}
.leaflet-container,.folium-map{display:none}
}
"""

_ADDRESS_LIST_JS = """
(function () {
  var STORAGE_KEY = '__STORAGE_KEY__';
  var VISITED_COLOR = '__VISITED_COLOR__';
  function ready(fn) {
    if (document.readyState !== 'loading') { fn(); }
    else { document.addEventListener('DOMContentLoaded', fn); }
  }
  function loadVisited() {
    try { return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}'); }
    catch (err) { return {}; }
  }
  function saveVisited(visited) {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(visited)); }
    catch (err) {}
  }
  ready(function () {
    var map = window['__MAP_NAME__'];
    var panel = document.getElementById('addrmap-list');
    if (!panel) { return; }
    var items = Array.prototype.slice.call(panel.querySelectorAll('.addrmap-item'));
    var toggle = panel.querySelector('.addrmap-toggle');
    var visited = loadVisited();

    function pointKey(item) {
      // Only the coordinates identify an address across map regenerations.
      return item.getAttribute('data-lat') + ',' + item.getAttribute('data-lng');
    }
    function setVisited(item, checked, persist) {
      item.classList.toggle('addrmap-visited', checked);
      var box = item.querySelector('.addrmap-check');
      if (box) { box.checked = checked; }
      if (persist) {
        visited[pointKey(item)] = checked;
        saveVisited(visited);
      }
    }
    function recolorMarker(item, checked) {
      if (!map) { return; }
      var lat = parseFloat(item.getAttribute('data-lat'));
      var lng = parseFloat(item.getAttribute('data-lng'));
      map.eachLayer(function (layer) {
        if (!(layer instanceof L.Marker)) { return; }
        var pos = layer.getLatLng();
        if (Math.abs(pos.lat - lat) < 1e-6 && Math.abs(pos.lng - lng) < 1e-6) {
          if (checked) {
            if (!layer._addrmapIcon) { layer._addrmapIcon = layer.options.icon; }
            layer.setIcon(L.divIcon({
              className: 'addrmap-marker-pin',
              html: '<svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">' +
                    '<path d="M12.5 0C5.6 0 0 5.6 0 12.5 0 21.4 12.5 41 12.5 41S25 21.4 25 12.5C25 5.6 19.4 0 12.5 0Z" ' +
                    'fill="' + VISITED_COLOR + '" stroke="#fff" stroke-width="1.5"/>' +
                    '<circle cx="12.5" cy="12.5" r="4" fill="rgba(255,255,255,.85)"/></svg>',
              iconSize: [25, 41], iconAnchor: [12, 40], popupAnchor: [0, -36]
            }));
          } else if (layer._addrmapIcon) {
            layer.setIcon(layer._addrmapIcon);
          }
        }
      });
    }
    function openEntry(item) {
      var lat = parseFloat(item.getAttribute('data-lat'));
      var lng = parseFloat(item.getAttribute('data-lng'));
      if (isNaN(lat) || isNaN(lng) || !map) { return; }
      map.flyTo([lat, lng], __FLY_ZOOM__);
      var found = null;
      map.eachLayer(function (layer) {
        if (!found && layer instanceof L.Marker) {
          var pos = layer.getLatLng();
          if (Math.abs(pos.lat - lat) < 1e-6 && Math.abs(pos.lng - lng) < 1e-6) {
            found = layer;
          }
        }
      });
      if (found) { found.openPopup(); }
    }
    items.forEach(function (item) {
      var box = item.querySelector('.addrmap-check');
      if (box) {
        box.addEventListener('click', function (event) {
          event.stopPropagation();
        });
        box.addEventListener('change', function () {
          setVisited(item, box.checked, true);
          recolorMarker(item, box.checked);
        });
      }
      var entry = item.querySelector('.addrmap-entry');
      if (entry) {
        entry.addEventListener('click', function () { openEntry(item); });
      }
      if (visited[pointKey(item)]) {
        setVisited(item, true, false);
        recolorMarker(item, true);
      }
    });
    if (toggle) {
      toggle.addEventListener('click', function () {
        panel.classList.toggle('addrmap-collapsed');
        toggle.textContent = panel.classList.contains('addrmap-collapsed') ? '+' : '\\u2013';
      });
    }
  });
})();
"""


def _cell_text(row, column):
    """Return a printable string for row[column]; empty if missing."""
    if column not in row.index or pd.isna(row[column]):
        return ""
    return str(row[column]).strip()


def add_address_list(map_obj, df, color=None, filter_col=None, title=None):
    """Attach an interactive address list panel to a Folium map.

    The panel is rendered directly in the map HTML (no extra files): each
    entry has a checkbox to mark the address as visited/considered (for
    e.g. magazine or flyer distribution), turns green and recolors the
    map marker accordingly, and persists via localStorage. Clicking an
    entry flies the map to the corresponding marker and opens its popup.
    Print styles turn the panel into a plain, full-page address list; the
    PNG tables generated by generate_filter_maps stay in sync only in
    content, not in visited state.

    Parameters
    ----------

    map_obj : folium.Map
        Map to attach the list to.
    df : pd.DataFrame
        Data with canonical column names (Street, Number, PostalCode,
        City, Name, Group, Latitude, Longitude).
    color : str | None, optional
        Color key from :data:`MARKER_COLORS` used for the entry dots;
        None uses blue (or the per-group color when filter_col is given).
    filter_col : str | None, optional
        Column used to color entries per group (same colors as the
        markers in :func:`generate_group_map`).
    title : str | None, optional
        Panel header; defaults to "Addresses".

    Returns
    -------

    folium.Map
        The map the list was added to.
    """
    group_colors = {}
    if filter_col in df.columns:
        # Mirror the sorted group order used by generate_group_map so entry
        # dots always match marker colors.
        for group_index, (group_name, _) in enumerate(df.groupby(filter_col, sort=True)):
            group_colors[str(group_name)] = MARKER_COLORS[
                group_index % len(MARKER_COLORS)
            ]

    items = []
    for _, row in _sorted_marker_rows(df):
        name = _cell_text(row, NAME)
        street_line = " ".join(
            part
            for part in (_cell_text(row, STREET), _cell_text(row, NUMBER))
            if part
        )
        city_line = " ".join(
            part
            for part in (_cell_text(row, POSTAL_CODE), _cell_text(row, CITY))
            if part
        )
        group_name = _cell_text(row, filter_col if filter_col in row.index else "")
        dot_color = (
            color
            if color is not None
            else group_colors.get(group_name)
        )
        if dot_color is not None:
            dot_color = _MARKER_HEX.get(dot_color, _DEFAULT_DOT_COLOR)
        else:
            dot_color = _DEFAULT_DOT_COLOR

        item_lines = [f'<span class="addrmap-name">{html.escape(name) or "&nbsp;"}</span>']
        if street_line:
            item_lines.append(
                f'<span class="addrmap-street">{html.escape(street_line)}</span>'
            )
        if city_line:
            item_lines.append(
                f'<span class="addrmap-city">{html.escape(city_line)}</span>'
            )
        if group_name:
            item_lines.append(
                f'<span class="addrmap-group">{html.escape(group_name)}</span>'
            )
        items.append(
            '<li class="addrmap-item" '
            f'data-lat="{row[LATITUDE]:.6f}" data-lng="{row[LONGITUDE]:.6f}">'
            f'<input class="addrmap-check" type="checkbox" '
            'aria-label="Mark address as visited"/><span class="addrmap-dot" '
            f'style="background:{dot_color};"></span>'
            f'<span class="addrmap-entry">{"".join(item_lines)}</span></li>'
        )

    count = len(items)
    count_label = f"{count} address" if count == 1 else f"{count} addresses"
    header = html.escape(str(title if title else "Addresses") or "Addresses")
    list_html = f"""<style>{_ADDRESS_LIST_CSS.replace("__VISITED_COLOR__", _VISITED_COLOR)}</style>
<div id="addrmap-list" class="addrmap-collapsed">
  <div class="addrmap-header">
    <button class="addrmap-toggle" type="button" title="Show / hide list">+</button>
  </div>
  <div class="addrmap-title">{header} &middot; {count_label}</div>
  <ul class="addrmap-items">{''.join(items)}</ul>
</div>
<script>
{_ADDRESS_LIST_JS.replace("__MAP_NAME__", map_obj.get_name()).replace("__FLY_ZOOM__", str(DEFAULT_LIST_ZOOM)).replace("__STORAGE_KEY__", f"addrmap-visited-{map_obj.get_name()}").replace("__VISITED_COLOR__", _VISITED_COLOR)}
</script>"""

    # Branca renders child elements through Jinja, which would choke on CSS/JS
    # brace sequences like "{#"; a raw block keeps the markup verbatim.
    map_obj.get_root().html.add_child(Element(f"{{% raw %}}{list_html}{{% endraw %}}"))
    return map_obj


def generate_global_map(
    df,
    output_file="map.html",
    map_type=DEFAULT_MAP_TYPE,
    zoom_start=DEFAULT_MARKER_ZOOM,
    include_list=False,
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
    include_list : bool, optional
        Attach the interactive address list panel to the map.
        Off by default; mainly used by generate_filter_maps.

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

    if include_list:
        add_address_list(map_obj, valid_rows)

    map_obj.save(output_file)
    print(f"[OK] Map saved to: {output_file}")
    return os.path.abspath(output_file)


def generate_group_map(
    df,
    filter_col=GROUP,
    output_file="map_groups.html",
    map_type=DEFAULT_MAP_TYPE,
    zoom_start=DEFAULT_GROUP_ZOOM,
    include_list=False,
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
    include_list : bool, optional
        Attach the interactive address list panel to the map.
        Off by default; mainly used by generate_filter_maps.

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

    if include_list:
        add_address_list(map_obj, valid_rows, filter_col=filter_col)

    map_obj.save(output_file)
    print(f"[OK] Map saved to: {output_file}")
    return os.path.abspath(output_file)


def _save_address_table_png(rows, group_name, output_dir):
    """Render the addresses of one group as a printable PNG table.

    Parameters
    ----------

    rows : pd.DataFrame
        Rows of the group (canonical column names).
    group_name : str
        Group name used in the table title.
    output_dir : str
        Directory to write the PNG into.

    Returns
    -------
    str
        Absolute path of the written PNG file.
    """
    table_rows = rows[[STREET, NUMBER, NAME]].fillna("")
    table_data = [
        [row[STREET], row[NUMBER], row[NAME]]
        for _, row in table_rows.iterrows()
    ]
    table_data.sort(
        key=lambda entry: (
            str(entry[0]).lower(),
            _house_number_key(str(entry[1])),
            str(entry[2]).lower(),
        )
    )
    count = len(table_data)
    label = "address" if count == 1 else "addresses"

    figure_height = max(0.4 * count + 1.2, 2.0)
    fig, ax = plt.subplots(figsize=(8, figure_height))
    ax.axis("tight")
    ax.axis("off")
    ax.set_title(f"{group_name} - {count} {label}", fontsize=14, pad=12)

    table = ax.table(
        cellText=table_data,
        colLabels=[STREET, NUMBER, NAME],
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.2, 1.2)

    png_path = os.path.join(
        output_dir, f"locations_list_{sanitize_filename(group_name)}.png"
    )
    fig.savefig(png_path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"[OK] Address table saved to: {png_path}")
    return os.path.abspath(png_path)


def generate_filter_maps(
    df, filter_col=GROUP, output_dir="out", map_type=DEFAULT_MAP_TYPE
):
    """Create one interactive map per group, each with an address list.

    Each group also gets a printable PNG table of its addresses. The
    interactive list always includes one visited checkbox per address
    to mark addresses as already visited (e.g. when distributing
    magazines or flyers); checking it recolors the marker on the map.

    Parameters
    ----------

    df : pd.DataFrame
        Data with canonical column names.
    filter_col : str, optional
        Column used to group addresses (e.g. Group).
    output_dir : str, optional
        Directory to write the per-group maps into.
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
        add_address_list(map_obj, valid_rows, title=str(group_name))

        html_path = os.path.join(
            output_dir, f"map_{sanitize_filename(group_name)}.html"
        )
        map_obj.save(html_path)

        png_path = _save_address_table_png(valid_rows, str(group_name), output_dir)

        written_files[group_name] = {"html": html_path, "png": png_path}

    return written_files
