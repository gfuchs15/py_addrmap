"""Command line interface for addrmap.

Reads an Excel (or CSV) file of addresses, optionally renames localized
column names to the canonical English ones, geocodes the addresses and
generates maps. The output directory can be served over HTTP so that
OpenStreetMap tiles load reliably (see --serve).
"""

import argparse
import io
import os
import sys
from functools import partial

import pandas as pd

from .constants import (
    DEFAULT_LANGUAGE,
    DEFAULT_MAP_TYPE,
    DEFAULT_MIN_DELAY_S,
    DEFAULT_USER_AGENT,
    GROUP,
)
from .geocoding import geocode_df
from .gmapping import generate_global_map_gmplot
from .mapping import generate_filter_maps, generate_global_map, generate_group_map, TILES
from .utils import ensure_directory, normalize_columns, parse_column_map

MAP_TYPES = sorted(TILES)


def _make_console_print():
    """Return a print() that reconfigures the console to UTF-8 if needed.

    Windows consoles often default to a legacy code page (e.g. cp1252) that
    cannot encode all characters used in the CLI messages.
    """
    stream_kwargs = {}
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        # Fall back to a wrapped stream that replaces undecodable characters
        # instead of crashing the CLI.
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )
        stream_kwargs = {"file": sys.stdout}
    return partial(print, **stream_kwargs)


_print = _make_console_print()


def read_input_file(input_path, sheet_name=0):
    """Read an address table from Excel or CSV into a DataFrame."""
    extension = os.path.splitext(input_path)[1].lower()
    if extension == ".csv":
        return pd.read_csv(input_path)
    return pd.read_excel(input_path, sheet_name=sheet_name)


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        prog="addrmap",
        description=(
            "addrmap - Generate maps from a list of addresses.\n"
            "Reads addresses, optionally renames localized columns to English, "
            "geocodes them, stores coordinates, generates maps with "
            "an interactive address list with visited checkboxes "
            "on per-group maps, plus printable PNG address tables. "
            "The output can be served "
            "via a local web server so OpenStreetMap tiles load without "
            "'403 Forbidden' errors."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-i",
        "--input",
        type=str,
        required=True,
        help="Path to the input Excel/CSV file containing address data",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=0,
        help="Sheet name (or index) to read from the input Excel file",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default="out",
        help="Directory to save the output file and maps",
    )
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default=DEFAULT_LANGUAGE,
        help=(
            "Built-in column alias preset used to rename localized input "
            "columns (e.g. Strasse -> Street) to the canonical English names"
        ),
    )
    parser.add_argument(
        "--column_map",
        type=str,
        default=None,
        help=(
            "Custom column renames applied before the language preset, "
            "as 'OldName=NewName' pairs separated by commas, "
            "e.g. 'Quartier=Group,Ortsteil=Group'"
        ),
    )
    parser.add_argument(
        "-f",
        "--filter",
        type=str,
        default=GROUP,
        help="Column name to group addresses by for per-group maps",
    )
    parser.add_argument(
        "-m",
        "--map_type",
        type=str,
        default=DEFAULT_MAP_TYPE,
        choices=MAP_TYPES,
        help="Style/tile provider for the maps",
    )
    parser.add_argument(
        "--min_delay_s",
        type=float,
        default=DEFAULT_MIN_DELAY_S,
        help=(
            "Minimum delay in seconds between geocoding requests to comply "
            "with Nominatim's usage policy"
        ),
    )
    parser.add_argument(
        "--user_agent",
        type=str,
        default=DEFAULT_USER_AGENT,
        help="Identifying user agent for Nominatim geocoding",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="Google Maps API key; the gmplot map is skipped when omitted",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help=(
            "Serve the output directory over HTTP (http://localhost:8000) "
            "after generation, so browsers send a Referer and OpenStreetMap "
            "tiles no longer fail with '403 Forbidden'"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port used by --serve",
    )
    parser.add_argument(
        "--skip_geocode",
        action="store_true",
        help="Skip geocoding (e.g. when the input already has coordinates)",
    )

    return parser.parse_args(argv)


def serve_directory(directory, port):
    """Serve *directory* over HTTP until interrupted (blocks)."""
    import http.server
    import socketserver

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with socketserver.TCPServer(("", port), handler) as httpd:
        _print(f"[SERVE] Serving {directory} at http://localhost:{port} (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            _print("\n[STOP] Server stopped.")


def run_pipeline(args):
    """Execute the full pipeline described by parsed CLI arguments."""
    if not os.path.exists(args.input):
        _print(f"❌ ERROR: Input file not found: {args.input}")
        sys.exit(1)

    _print(f"[READ] Reading addresses from: {args.input}")
    try:
        df = read_input_file(args.input, sheet_name=args.sheet)
    except Exception as error:
        _print(f"❌ ERROR: Could not read input file: {error}")
        sys.exit(1)

    try:
        custom_map = parse_column_map(args.column_map)
        df = normalize_columns(df, language=args.language, column_map=custom_map)
    except ValueError as error:
        _print(f"❌ ERROR: {error}")
        sys.exit(1)

    ensure_directory(args.output_dir)

    if args.skip_geocode:
        _print("===[SKIP] Skipping geocoding (--skip_geocode)===")
    else:
        _print("===Geocoding addresses...===")
        df = geocode_df(
            df,
            min_delay_s=args.min_delay_s,
            user_agent=args.user_agent,
            output_csv=os.path.join(args.output_dir, "geocoded_partial.csv"),
        )

    output_path = os.path.join(args.output_dir, "enriched_addresses.xlsx")
    _print(f"[OK] Saving enriched Excel file to: {output_path}")
    df.to_excel(output_path, index=False)

    _print("===Generating global map...===")
    generate_global_map(
        df,
        output_file=os.path.join(args.output_dir, "map.html"),
        map_type=args.map_type,
    )

    if args.filter in df.columns:
        _print(f"===Generating per-group maps for column '{args.filter}'...===")
        generate_group_map(
            df,
            filter_col=args.filter,
            output_file=os.path.join(args.output_dir, "map_groups.html"),
            map_type=args.map_type,
        )
        generate_filter_maps(
            df,
            filter_col=args.filter,
            output_dir=args.output_dir,
            map_type=args.map_type,
        )
    else:
        _print(f"⚠️ WARNING: Column '{args.filter}' not found - skipping per-group maps")

    if args.api_key:
        generate_global_map_gmplot(
            df,
            api_key=args.api_key,
            output_file=os.path.join(args.output_dir, "map_google.html"),
        )
    else:
        _print("===[SKIP] Skipping Google map (no --api_key given)===")

    _print("✔ Done! All maps and tables generated.")

    if args.serve:
        serve_directory(os.path.abspath(args.output_dir), args.port)


def main():
    try:
        run_pipeline(parse_arguments())
    except KeyboardInterrupt:
        _print("\n🛑 Aborted by user.")
        sys.exit(130)
    except (ValueError, FileNotFoundError) as error:
        _print(f"❌ ERROR: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
