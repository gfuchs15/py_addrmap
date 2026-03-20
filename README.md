# addrmap

`addrmap` is a Python tool that reads an Excel file of addresses, geocodes them, adds latitude/longitude coordinates, generates interactive Folium maps (e.g. using Open Street Map tile provide), and produces list of addresses to print.

The mapping can be filtered by quarters.

## Features
- Read addresses from Excel
- Geocode with Nominatim
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

## Usage (CLI)
```
addrmap[.exe] --help
```
example:
```
addrmap[.exe] -i ./examples/berlin_addresses.xlsx -o ./examples/berlin_out
```
## Excel Format
Following columns are required: Strasse, Nummer, PLZ, City, Name.

## Python Example
```python
import pandas as pd
from addrmap.geocoding import geocode_df
from addrmap.mapping import generate_main_map, generate_quarter_maps

df = pd.read_excel("address.xlsx")
df = geocode_df(df)
generate_main_map(df, output_file="map.html")
generate_quarter_maps(df, filter_col="Viertel", output_dir="./out")
```

## Known issues/Remarks
- When using the default OpenStreetMap (OSM) tiles in Folium, the application may display a “403 Forbidden” error on generated maps. This typically occurs when the OSM Tile Usage Policy is violated and access to the tiles is temporarily blocked. You can avoid this issue by selecting an alternative tile provider with the `-m` option, for example: `-m esri_street` or `-m cartodb`
- Geocoding (retrieving latitude and longitude coordinates) may take some time because a default 2‑second delay is applied to be sure to comply with Nominatim’s usage policy. You can adjust or reduce this delay using teh command line option as for example `--min_delay_s 1`.

---
Copyright (c) 2026 Guillaume Fuchs - [MIT license](./LICENSE)
