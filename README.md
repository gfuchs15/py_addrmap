# addrmap

`addrmap` is a Python tool that reads an Excel file of addresses, geocodes them, adds latitude/longitude coordinates, generates interactive Folium maps (e.g. using Open Street Map tile provide), and produces list of addresses to print.

The mapping can be filtered by quarters.

Copyright (c) 2026 Guillaume Fuchs - [MIT license](./LICENSE)

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
Columns required: Strasse, Nummer, PLZ, City, Name, Viertel.

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

## Known issues
- "A 403 Forbidden error" windows on generated maps when using default OpenStreetMap (OSM) tiles in Folium. Application has then been blocked, usually due to violating the Tile Usage Policy. It can be circonvened by using other tile providers using option '-m', e.g. '-m esri_street' of '-m cartodb'.
- Geocode (getting latiture and longitude coordinates) can take some times, since a default delay of 2s is set espect Nominatim's usage policy. Delay can be adjusted and decreased with option, like '-min_delay_s 1'.
