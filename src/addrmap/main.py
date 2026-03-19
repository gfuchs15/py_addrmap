import argparse
import pandas as pd
import os
import sys
from .geocoding import geocode_df
from .mapping import generate_global_map, generate_filter_maps


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="addrmap",
        description=(
            "addrmap — Generate maps and tables from an Excel list of addresses.\n"
            "Reads addresses, geocodes them, stores coordinates, generates maps "
            "and per-quarter PNG tables."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-i",
        "--input",
        type=str,
        required=True,
        help="Path to the input Excel file containing address data",
    )

    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default="out",
        help="Directory to save the output Excel file and maps",
    )
    parser.add_argument(
        "-f",
        "--filter",
        type=str,
        default="Viertel",
        help="Column name to filter addresses for per-quarter maps",
    )
    parser.add_argument(
        "-m",
        "--map_type",
        type=str,
        default="osm",
        choices=["esri_street", "cartodb", "osm"],
        help="Style/Tile provider for the maps",
    )
    parser.add_argument(
        "--min_delay_s",
        type=float,
        default=2.0,
        help="Minimum delay in seconds between geocoding requests to respect Nominatim's usage policy",
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    if not os.path.exists(args.input):
        print(f"❌ ERROR: Input file not found: {args.input}")
        sys.exit(1)

    print(f"📄 Reading addresses from: {args.input}")
    df = pd.read_excel(args.input)

    print("📍 Geocoding addresses…")
    df = geocode_df(df, min_delay_s=args.min_delay_s)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    output_path = os.path.join(args.output_dir, "enriched_addresses.xlsx")
    print(f"💾 Saving enriched Excel file to: {output_path}")
    df.to_excel(output_path, index=False)

    print("🗺️ Generating global map…")
    generate_global_map(
        df,
        output_file=os.path.join(args.output_dir, "map.html"),
        map_type=args.map_type,
    )

    print("🗺️ Generating per‑quarter maps…")
    generate_filter_maps(
        df,
        filter_col=args.filter,
        output_dir=args.output_dir,
        map_type=args.map_type,
    )

    print("✔ Done! All maps and tables generated.")


if __name__ == "__main__":
    main()
