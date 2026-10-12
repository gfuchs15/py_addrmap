# addrmap

`addrmap` is a Python tool that reads an Excel or CSV file of addresses, geocodes them, adds latitude/longitude coordinates, generates interactive Folium maps, and produces list of addresses to print.

The mapping can be filtered by quarters/groups.

## Features
- Read addresses from Excel or CSV
- Geocode with Nominatim (with address fallbacks, progress bar and checkpoint resume)
- Internally uses consistent English column names: `Street`, `Number`, `PostalCode`, `City`, `Name`, `Group`, `Latitude`, `Longitude`
- Rename localized input columns (e.g. German `Strasse`, `PLZ`, `Viertel`) automatically or via a custom mapping
- Generate HTML maps and PNG tables with Folium
- CLI: `addrmap`

## Installation
```
pip install .
```
optionally in editable mode
```
pip install -e .
```
with the optional Google Maps (gmplot) support:
```
pip install ".[google]"
```

## Usage (CLI)
```
addrmap[.exe] --help
```
example:
```
addrmap[.exe] -i ./examples/berlin_addresses.xlsx -o ./examples/berlin_out
```

### Column name mapping
The canonical column names are English. If your file uses localized headers
(e.g. German), they are renamed automatically before processing:

- `-l/--language` — built-in preset, default `german` maps
  `Strasse→Street`, `Nummer→Number`, `PLZ→PostalCode`, `Stadt/Ort→City`,
  `Viertel/Bezirk→Group`, `Breitengrad→Latitude`, `Längengrad→Longitude`.
  Pass `-l ""` to skip the preset.
- `--column_map` — arbitrary `OldName=NewName` pairs (comma separated),
  applied to the raw headers, e.g. `--column_map "Quartier=Group,Badstrasse=Street"`
- `-m/--map_type` — tile provider, one of `osm`, `esri_street`, `carto`
  (default `esri_street`)

### Other options
- `--sheet` — Excel sheet name/index to read
- `-f/--filter` — column to group addresses by (default `Group`)
- `--min_delay_s` — Nominatim rate-limit delay (default 2 s)
- `--user_agent` — identifying user agent for Nominatim
- `--api_key` — Google Maps API key for the optional gmplot map
- `--skip_geocode` — skip geocoding when the input already has coordinates
- `--serve [--port 8000]` — serve the output directory over local HTTP after
  generation (see below)

## Excel Format
Following columns are required: `Street`, `Number`, `PostalCode`, `City`, `Name`.
Localized names such as `Strasse`, `Nummer`, `PLZ`, `City`, `Name`, `Viertel`
are accepted and renamed automatically; any other renaming can be done via
`--column_map`.

After geocoding, the columns `Latitude` and `Longitude` are added.

## Python Example
```python
import pandas as pd
from addrmap.geocoding import geocode_df
from addrmap.mapping import generate_global_map, generate_filter_maps

df = pd.read_excel("address.xlsx")
# rename German columns instead:
# from addrmap.utils import normalize_columns
# df = normalize_columns(df, language="german")
df = geocode_df(df)
generate_global_map(df, output_file="map.html")
generate_filter_maps(df, filter_col="Group", output_dir="./out")
```

## Known issues/Remarks

### OSM “403 Forbidden”
When using the OpenStreetMap (OSM) tiles in Folium, the application may show
“403 Forbidden” on generated maps. Root cause: OSM's tile usage policy requires
browsers to send a valid `Referer` header. Opening the generated HTML directly
from disk (`file://`) sends no `Referer`, so the tile server rejects the
requests. Ways to avoid it:

1. Serve the output directory over HTTP with the `--serve` option and open the
   map via `http://localhost:8000` instead of `file://`. The browser then sends
   a proper `Referer` and OSM tiles load normally.
   (Equivalent manual command: `python -m http.server 8000 -d out`)
2. Select an alternative tile provider with the `-m` option
   (default is already `esri_street`), e.g. `-m esri_street` or `-m carto`.

Note: geocoding itself (Nominatim) is not affected by this issue; it is purely
about loading map tiles in the browser.

### Geocoding delay
Geocoding may take some time because a default 2-second delay is applied to
comply with Nominatim's usage policy. You can adjust it with `--min_delay_s`,
e.g. `--min_delay_s 1`.

---
Copyright (c) 2026 Guillaume Fuchs - [MIT license](./LICENSE)
