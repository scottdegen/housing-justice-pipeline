"""
Housing Justice Pipeline — Choropleth Maps

Downloads Census TIGER/Line county shapefile, merges the pipeline output
on FIPS codes, and produces four choropleth maps saved to output/figures/.

Usage:
    python choropleth.py

Requires: geopandas, mapclassify
    pip install geopandas mapclassify
"""

import io
import zipfile
from pathlib import Path

import geopandas as gpd
import mapclassify
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

# ── Config ─────────────────────────────────────────────────────────────────────

INPUT_CSV   = Path("output/housing_justice_county.csv")
FIGURES_DIR = Path("output/figures")
SHAPEFILE_CACHE = Path("output/counties.shp")

# Census 20m generalized county shapefile — small enough to download each run
TIGER_URL = (
    "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_county_20m.zip"
)

# Albers Equal Area Conic — standard for US county choropleths
CONUS_CRS = "EPSG:5070"

# FIPS codes to drop for continental US maps (AK=02, HI=15, PR=72, territories)
NON_CONUS = {"02", "15", "60", "66", "69", "72", "78"}

plt.rcParams.update({
    "font.family":     "sans-serif",
    "font.size":       10,
    "figure.dpi":      150,
})

# ── Data loading ───────────────────────────────────────────────────────────────

def load_shapefile() -> gpd.GeoDataFrame:
    """Download and return the Census county shapefile, cached locally."""
    if SHAPEFILE_CACHE.exists():
        print("  shapefile → loading from cache")
        return gpd.read_file(SHAPEFILE_CACHE)

    print("  shapefile → downloading from Census TIGER...")
    resp = requests.get(TIGER_URL, timeout=120)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(SHAPEFILE_CACHE.parent / "tiger_tmp")

    shp_path = next((SHAPEFILE_CACHE.parent / "tiger_tmp").glob("*.shp"))
    gdf = gpd.read_file(shp_path)
    gdf.to_file(SHAPEFILE_CACHE)
    print(f"  shapefile → {len(gdf)} counties loaded")
    return gdf


def build_geodataframe() -> gpd.GeoDataFrame:
    """Merge pipeline CSV onto county geometries, project to Albers."""
    gdf = load_shapefile()
    df  = pd.read_csv(INPUT_CSV, dtype={"fips": str})
    df["fips"] = df["fips"].str.zfill(5)

    # TIGER uses GEOID for the 5-digit county FIPS
    merged = gdf.merge(df, left_on="GEOID", right_on="fips", how="left")

    # Drop non-CONUS for cleaner maps
    conus = merged[~merged["STATEFP"].isin(NON_CONUS)].copy()
    conus = conus.to_crs(CONUS_CRS)

    print(f"  merged → {len(conus)} CONUS counties, {conus['fips'].notna().sum()} with data")
    return conus

# ── Map helpers ────────────────────────────────────────────────────────────────

def _base_fig(title: str, note: str):
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    ax.set_axis_off()
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    fig.text(0.01, 0.02, note, fontsize=7.5, color="gray", wrap=True)
    return fig, ax


def _draw_states(ax, gdf: gpd.GeoDataFrame) -> None:
    """Overlay state boundaries for reference."""
    states = gdf.dissolve(by="STATEFP").boundary
    states.plot(ax=ax, linewidth=0.5, edgecolor="#aaaaaa")

# ── Maps ───────────────────────────────────────────────────────────────────────

def map_severe_rent_burden(gdf: gpd.GeoDataFrame) -> None:
    col = "severe_rent_burden_rate"
    sub = gdf.dropna(subset=[col]).copy()

    classifier = mapclassify.Quantiles(sub[col], k=5)
    bins = [sub[col].min()] + list(classifier.bins)
    labels = []
    for i in range(len(bins) - 1):
        lo, hi = round(bins[i] * 100), round(bins[i + 1] * 100)
        if i == 0:
            labels.append(f"Under {hi}% of renters")
        elif i == len(bins) - 2:
            labels.append(f"{lo}%+ of renters")
        else:
            labels.append(f"{lo}% – {hi}% of renters")

    fig, ax = _base_fig(
        "Severe Rent Burden by U.S. County\nShare of renters paying 50%+ of income on rent",
        "Source: U.S. Census ACS 5-Year (2022). CONUS only. Each band = 20% of counties (quantile classification).",
    )
    sub.plot(
        column=col,
        ax=ax,
        scheme="quantiles",
        k=5,
        cmap="YlOrRd",
        legend=True,
        legend_kwds={
            "title":    "Severely cost-burdened renters",
            "labels":   labels,
            "loc":      "lower left",
            "fontsize": 8,
        },
        missing_kwds={"color": "#eeeeee", "label": "No data"},
        linewidth=0.05,
        edgecolor="#cccccc",
    )
    _draw_states(ax, gdf)
    fig.savefig(FIGURES_DIR / "09_choropleth_rent_burden.png", bbox_inches="tight")
    plt.close(fig)
    print("  saved → output/figures/09_choropleth_rent_burden.png")


def map_jail_rate(gdf: gpd.GeoDataFrame) -> None:
    col = "jail_pop_rate_per100k"
    sub = gdf.dropna(subset=[col]).copy()

    # Cap top 1% — small counties with regional jails can have extreme rates
    cap = sub[col].quantile(0.99)
    sub[col] = sub[col].clip(upper=cap)

    # Compute bins manually so we can write readable legend labels
    classifier = mapclassify.Quantiles(sub[col], k=5)
    bins = [sub[col].min()] + list(classifier.bins)
    labels = []
    for i in range(len(bins) - 1):
        lo, hi = int(round(bins[i])), int(round(bins[i + 1]))
        if i == 0:
            labels.append(f"Under {hi:,} per 100k")
        elif i == len(bins) - 2:
            labels.append(f"{lo:,}+ per 100k")
        else:
            labels.append(f"{lo:,} – {hi:,} per 100k")

    fig, ax = _base_fig(
        "Jail Population Rate by U.S. County\nJail residents per 100,000 people",
        f"Source: Vera Institute Incarceration Trends. CONUS only. "
        f"Top 1% capped at {int(cap):,} per 100k. Each band = 20% of counties (quantile classification).",
    )
    sub.plot(
        column=col,
        ax=ax,
        scheme="quantiles",
        k=5,
        cmap="PuRd",
        legend=True,
        legend_kwds={
            "title":    "Jail population rate",
            "labels":   labels,
            "loc":      "lower left",
            "fontsize": 8,
        },
        missing_kwds={"color": "#eeeeee", "label": "No data"},
        linewidth=0.05,
        edgecolor="#cccccc",
    )
    _draw_states(ax, gdf)
    fig.savefig(FIGURES_DIR / "10_choropleth_jail_rate.png", bbox_inches="tight")
    plt.close(fig)
    print("  saved → output/figures/10_choropleth_jail_rate.png")


def map_racial_disparity(gdf: gpd.GeoDataFrame) -> None:
    df = gdf.copy()
    mask = (df["white_jail_rate_per100k"] > 0) & df["black_jail_rate_per100k"].notna()
    df.loc[mask, "disparity_ratio"] = (
        df.loc[mask, "black_jail_rate_per100k"] / df.loc[mask, "white_jail_rate_per100k"]
    )

    sub = df.dropna(subset=["disparity_ratio"]).copy()
    # Cap at 20x for color scale readability
    sub["disparity_ratio"] = sub["disparity_ratio"].clip(upper=20)

    median = sub["disparity_ratio"].median()

    classifier = mapclassify.Quantiles(sub["disparity_ratio"], k=5)
    bins = [sub["disparity_ratio"].min()] + list(classifier.bins)
    labels = []
    for i in range(len(bins) - 1):
        lo, hi = round(bins[i], 1), round(bins[i + 1], 1)
        if i == 0:
            labels.append(f"Under {hi}x (near parity)")
        elif i == len(bins) - 2:
            labels.append(f"{lo}x+ more likely")
        else:
            labels.append(f"{lo}x – {hi}x more likely")

    fig, ax = _base_fig(
        "Racial Disparity in Jail Rates by U.S. County\nBlack jail rate ÷ White jail rate",
        f"Source: Vera Institute. CONUS only. Median: Black residents are {median:.1f}x more likely to be jailed than white residents. "
        f"Ratio capped at 20x. Each band = 20% of counties.",
    )
    sub.plot(
        column="disparity_ratio",
        ax=ax,
        scheme="quantiles",
        k=5,
        cmap="RdPu",
        legend=True,
        legend_kwds={
            "title":    "Black/white jail rate ratio",
            "labels":   labels,
            "loc":      "lower left",
            "fontsize": 8,
        },
        missing_kwds={"color": "#eeeeee", "label": "No data / single-race county"},
        linewidth=0.05,
        edgecolor="#cccccc",
    )
    _draw_states(ax, gdf)
    fig.savefig(FIGURES_DIR / "11_choropleth_racial_disparity.png", bbox_inches="tight")
    plt.close(fig)
    print("  saved → output/figures/11_choropleth_racial_disparity.png")


def map_dual_burden(gdf: gpd.GeoDataFrame) -> None:
    """Highlight counties in the top quintile for BOTH rent burden and jail rate."""
    df = gdf.copy()

    burden_thresh = df["severe_rent_burden_rate"].quantile(0.80)
    jail_thresh   = df["jail_pop_rate_per100k"].quantile(0.80)

    df["category"] = "Other counties"
    df.loc[df["severe_rent_burden_rate"] >= burden_thresh, "category"] = "High housing burden"
    df.loc[df["jail_pop_rate_per100k"]   >= jail_thresh,   "category"] = "High incarceration"
    df.loc[
        (df["severe_rent_burden_rate"] >= burden_thresh) &
        (df["jail_pop_rate_per100k"]   >= jail_thresh),
        "category"
    ] = "Both"

    n_dual = (df["category"] == "Both").sum()

    color_map = {
        "Other counties":       "#d4d4d4",
        "High housing burden":  "#f4a261",
        "High incarceration":   "#9b72cf",
        "Both":                 "#e63946",
    }

    fig, ax = _base_fig(
        f"Counties with High Housing Burden AND High Incarceration (n={n_dual})",
        "80th percentile threshold for each dimension. "
        "Source: Census ACS (2022), Vera Institute. CONUS only.",
    )

    for cat, color in color_map.items():
        subset = df[df["category"] == cat]
        if not subset.empty:
            subset.plot(ax=ax, color=color, linewidth=0.05, edgecolor="#cccccc")

    # Manual legend
    patches = [
        mpatches.Patch(color=c, label=l)
        for l, c in color_map.items()
    ]
    ax.legend(
        handles=patches, loc="lower left", fontsize=9,
        title="County type", title_fontsize=9, framealpha=0.8,
    )
    _draw_states(ax, gdf)
    fig.savefig(FIGURES_DIR / "12_choropleth_dual_burden.png", bbox_inches="tight")
    plt.close(fig)
    print("  saved → output/figures/12_choropleth_dual_burden.png")

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not INPUT_CSV.exists():
        print(f"Error: {INPUT_CSV} not found. Run pipeline.py first.")
        return

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Building GeoDataFrame...")
    gdf = build_geodataframe()

    print("\nGenerating choropleth maps...")
    map_severe_rent_burden(gdf)
    map_jail_rate(gdf)
    map_racial_disparity(gdf)
    map_dual_burden(gdf)

    print(f"\nAll maps saved to {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
