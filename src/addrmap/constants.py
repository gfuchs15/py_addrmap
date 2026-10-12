"""Shared constants for addrmap.

Canonical column names are English. Input files with localized column
names (e.g. German) are normalized to these names before processing.
"""

# ----------------------------------------------------------
# Canonical (English) column names
# ----------------------------------------------------------
STREET = "Street"
NUMBER = "Number"
POSTAL_CODE = "PostalCode"
CITY = "City"
NAME = "Name"
GROUP = "Group"
VALID = "Valid"
LATITUDE = "Latitude"
LONGITUDE = "Longitude"

REQUIRED_ADDRESS_COLUMNS = (STREET, NUMBER, POSTAL_CODE, CITY, NAME)
COORDINATE_COLUMNS = (LATITUDE, LONGITUDE)

# ----------------------------------------------------------
# Built-in column alias presets: localized name -> canonical name
# ----------------------------------------------------------
COLUMN_ALIASES = {
    "german": {
        "Strasse": STREET,
        "Straße": STREET,
        "Nummer": NUMBER,
        "PLZ": POSTAL_CODE,
        "Plz": POSTAL_CODE,
        "Stadt": CITY,
        "Ort": CITY,
        "Name": NAME,
        "Viertel": GROUP,
        "Bezirk": GROUP,
        "Breitengrad": LATITUDE,
        "Längengrad": LONGITUDE,
        "Gueltig": VALID,
    },
}
DEFAULT_LANGUAGE = "german"

# ----------------------------------------------------------
# Geocoding defaults
# ----------------------------------------------------------
DEFAULT_USER_AGENT = "addrmap_geocoding_2026"
DEFAULT_MIN_DELAY_S = 2.0
DEFAULT_COUNTRY = "Germany"
DEFAULT_CHECKPOINT_FILE = "geocoded_partial.csv"
DEFAULT_SAVE_EVERY = 10

# ----------------------------------------------------------
# Mapping defaults
# ----------------------------------------------------------
DEFAULT_MAP_TYPE = "esri_street"
