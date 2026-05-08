"""
Housing Justice Pipeline — QGIS Export

Exports the pipeline output as a GeoPackage (.gpkg) and generates
QGIS layer style files (.qml) for the key variables so the data
opens pre-styled in QGIS as a choropleth.

Usage:
    python export_qgis.py          # export only
    python export_qgis.py --open   # export and launch QGIS

Output:
    output/housing_justice.gpkg    # open this in QGIS
    output/style_rent_burden.qml   # load via Layer > Load Layer Style
    output/style_jail_rate.qml
    output/style_racial_disparity.qml
"""

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path

import geopandas as gpd
import mapclassify
import numpy as np
import pandas as pd

INPUT_CSV       = Path("output/housing_justice_county.csv")
SHAPEFILE_CACHE = Path("output/counties.shp")
OUTPUT_GPKG     = Path("output/housing_justice.gpkg")
OUTPUT_DIR      = Path("output")

NON_CONUS = {"02", "15", "60", "66", "69", "72", "78"}
CONUS_CRS = "EPSG:5070"   # Albers Equal Area — matches choropleth.py

# ColorBrewer sequential palettes (5 classes), RGBA
YLORD_5 = ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"]
PURD_5  = ["#f1eef6", "#d7b5d8", "#df65b0", "#dd1c77", "#980043"]
RDPU_5  = ["#feebe2", "#fbb4b9", "#f768a1", "#c51b8a", "#7a0177"]


# ── Build GeoDataFrame ─────────────────────────────────────────────────────────

def build_geodataframe() -> gpd.GeoDataFrame:
    if not SHAPEFILE_CACHE.exists():
        print("Shapefile cache not found — run choropleth.py first to download it.")
        sys.exit(1)

    gdf = gpd.read_file(SHAPEFILE_CACHE)
    df  = pd.read_csv(INPUT_CSV, dtype={"fips": str})
    df["fips"] = df["fips"].str.zfill(5)

    merged = gdf.merge(df, left_on="GEOID", right_on="fips", how="left")
    conus  = merged[~merged["STATEFP"].isin(NON_CONUS)].copy()
    conus  = conus.to_crs(CONUS_CRS)

    # Derived column: racial disparity ratio
    mask = (conus["white_jail_rate_per100k"] > 0) & conus["black_jail_rate_per100k"].notna()
    conus.loc[mask, "disparity_ratio"] = (
        conus.loc[mask, "black_jail_rate_per100k"]
        / conus.loc[mask, "white_jail_rate_per100k"]
    ).clip(upper=20)

    print(f"  built → {len(conus)} CONUS counties, {conus['fips'].notna().sum()} with data")
    return conus


# ── GeoPackage export ──────────────────────────────────────────────────────────

def export_gpkg(gdf: gpd.GeoDataFrame) -> None:
    # Keep only the columns useful for QGIS exploration
    keep = [
        "geometry", "GEOID", "NAME", "STATEFP",
        "population", "poverty_rate",
        "rent_burden_rate", "severe_rent_burden_rate", "renter_rate",
        "jail_pop_rate_per100k", "prison_pop_rate_per100k",
        "black_jail_rate_per100k", "white_jail_rate_per100k", "disparity_ratio",
        "mental_health_distress_pct", "depression_pct",
    ]
    export_cols = [c for c in keep if c in gdf.columns]
    gdf[export_cols].to_file(OUTPUT_GPKG, driver="GPKG", layer="housing_justice")
    print(f"  exported → {OUTPUT_GPKG}  ({OUTPUT_GPKG.stat().st_size / 1024 / 1024:.1f} MB)")


# ── QML style file generation ──────────────────────────────────────────────────

def _rgba(hex_color: str, alpha: int = 255) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b},{alpha}"


def _qml(attr: str, ranges: list[tuple], colors: list[str], title: str) -> str:
    """Generate a minimal QGIS graduated color QML style string."""

    def symbol_block(idx: int, color: str) -> str:
        rgba = _rgba(color)
        return textwrap.dedent(f"""\
            <symbol alpha="1" clip_to_extent="1" force_rhr="0" name="{idx}" type="fill">
              <data_defined_properties><Option type="Map"><Option name="name" type="QString" value=""/><Option name="properties"/><Option name="type" type="QString" value="collection"/></Option></data_defined_properties>
              <layer class="SimpleFill" enabled="1" locked="0" pass="0">
                <Option type="Map">
                  <Option name="color" type="QString" value="{rgba}"/>
                  <Option name="outline_color" type="QString" value="204,204,204,255"/>
                  <Option name="outline_width" type="QString" value="0.1"/>
                  <Option name="style" type="QString" value="solid"/>
                </Option>
              </layer>
            </symbol>""")

    range_blocks = "\n".join(
        f'<range label="{label}" lower="{lo}" render="true" symbol="{i}" upper="{hi}"/>'
        for i, (lo, hi, label) in enumerate(ranges)
    )
    symbol_blocks = "\n".join(symbol_block(i, c) for i, c in enumerate(colors))

    return textwrap.dedent(f"""\
        <!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
        <qgis version="3.34" styleCategories="Symbology">
          <renderer-v2 attr="{attr}" enableorderby="0" forceraster="0"
                       graduatedMethod="GraduatedColor" type="graduatedSymbol">
            <ranges>{range_blocks}</ranges>
            <symbols>{symbol_blocks}</symbols>
            <source-symbol>
              <symbol alpha="1" clip_to_extent="1" force_rhr="0" name="0" type="fill">
                <layer class="SimpleFill" enabled="1" locked="0" pass="0">
                  <Option type="Map"><Option name="color" type="QString" value="125,125,125,255"/></Option>
                </layer>
              </symbol>
            </source-symbol>
            <colorramp name="[source]" type="gradient">
              <Option type="Map">
                <Option name="color1" type="QString" value="{_rgba(colors[0])}"/>
                <Option name="color2" type="QString" value="{_rgba(colors[-1])}"/>
              </Option>
            </colorramp>
            <legendformat format="0.4f"/>
          </renderer-v2>
          <blendMode>0</blendMode>
          <featureBlendMode>0</featureBlendMode>
          <layerGeometryType>2</layerGeometryType>
        </qgis>""")


def write_qml_styles(gdf: gpd.GeoDataFrame) -> None:
    styles = [
        {
            "attr":   "severe_rent_burden_rate",
            "file":   "style_rent_burden.qml",
            "colors": YLORD_5,
            "title":  "Severe rent burden",
            "fmt":    lambda lo, hi, i, n: (
                f"Under {round(hi*100)}% of renters" if i == 0
                else f"{round(lo*100)}%+ of renters" if i == n - 1
                else f"{round(lo*100)}% – {round(hi*100)}% of renters"
            ),
        },
        {
            "attr":   "jail_pop_rate_per100k",
            "file":   "style_jail_rate.qml",
            "colors": PURD_5,
            "title":  "Jail rate per 100k",
            "fmt":    lambda lo, hi, i, n: (
                f"Under {int(hi):,} per 100k" if i == 0
                else f"{int(lo):,}+ per 100k" if i == n - 1
                else f"{int(lo):,} – {int(hi):,} per 100k"
            ),
        },
        {
            "attr":   "disparity_ratio",
            "file":   "style_racial_disparity.qml",
            "colors": RDPU_5,
            "title":  "Black/white jail rate ratio",
            "fmt":    lambda lo, hi, i, n: (
                f"Under {hi:.1f}x (near parity)" if i == 0
                else f"{lo:.1f}x+ more likely" if i == n - 1
                else f"{lo:.1f}x – {hi:.1f}x more likely"
            ),
        },
    ]

    for s in styles:
        col = gdf[s["attr"]].dropna()
        if col.empty:
            print(f"  skipping {s['file']} — no data for {s['attr']}")
            continue

        # Cap jail rate at 99th percentile for classification (mirrors choropleth.py)
        if s["attr"] == "jail_pop_rate_per100k":
            col = col.clip(upper=col.quantile(0.99))

        classifier = mapclassify.Quantiles(col, k=5)
        bins = [col.min()] + list(classifier.bins)
        n = len(bins) - 1

        ranges = [
            (bins[i], bins[i + 1], s["fmt"](bins[i], bins[i + 1], i, n))
            for i in range(n)
        ]

        qml_content = _qml(s["attr"], ranges, s["colors"], s["title"])
        out_path = OUTPUT_DIR / s["file"]
        out_path.write_text(qml_content)
        print(f"  style   → {out_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true", help="Launch QGIS after export")
    args = parser.parse_args()

    if not INPUT_CSV.exists():
        print(f"Error: {INPUT_CSV} not found — run pipeline.py first.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)

    print("Building GeoDataFrame...")
    gdf = build_geodataframe()

    print("\nExporting GeoPackage...")
    export_gpkg(gdf)

    print("\nGenerating QGIS style files...")
    write_qml_styles(gdf)

    print(f"""
To open in QGIS:
  1. Open QGIS
  2. Layer > Add Layer > Add Vector Layer → select output/housing_justice.gpkg
  3. Layer > Load Layer Style → select a .qml file from output/
     style_rent_burden.qml       — severe rent burden by county
     style_jail_rate.qml         — jail population rate
     style_racial_disparity.qml  — Black/white disparity ratio
""")

    if args.open:
        gpkg_abs = OUTPUT_GPKG.resolve()
        subprocess.run(["open", "-a", "QGIS-final-4_0_2", str(gpkg_abs)])


if __name__ == "__main__":
    main()
