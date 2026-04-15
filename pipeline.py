"""
Housing Burden & Incarceration Pipeline

Pulls county-level housing cost burden data from the U.S. Census ACS API
and incarceration trend data from the Vera Institute, joins on FIPS county
codes, validates cross-source consistency, and writes a clean CSV.

Sources:
  Census ACS 5-Year (2022): https://api.census.gov
  Vera Institute Incarceration Trends:
    https://github.com/vera-institute/incarceration-trends

Usage:
  python pipeline.py
"""

import os
import sys
import logging
from io import StringIO
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv

from validate import run_validation

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────

CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
CENSUS_ENDPOINT = "https://api.census.gov/data/2022/acs/acs5"
VERA_URL = (
    "https://raw.githubusercontent.com/vera-institute/"
    "incarceration-trends/master/incarceration_trends_county.csv"
)

# CDC PLACES county-level health data (Socrata API — no key required)
CDC_PLACES_URL = "https://data.cdc.gov/resource/swc5-untb.json"
CDC_MEASURES = {
    "MHLTH":      "mental_health_distress_pct",   # Mental health not good ≥14 days
    "DEPRESSION": "depression_pct",               # Depression among adults
    "BINGE":      "binge_drinking_pct",           # Binge drinking
    "CSMOKING":   "current_smoking_pct",          # Current smoking
}
OUTPUT_DIR = Path("output")

# ACS variable codes → friendly column names.
# Source: https://api.census.gov/data/2022/acs/acs5/variables.json
ACS_VARS = {
    "B25070_001E": "renter_units_total",       # All renter-occupied units (cost burden denominator)
    "B25070_007E": "rent_burden_30_35pct",     # Paying 30.0–34.9% of income on rent
    "B25070_008E": "rent_burden_35_40pct",     # Paying 35.0–39.9%
    "B25070_009E": "rent_burden_40_50pct",     # Paying 40.0–49.9%
    "B25070_010E": "rent_burden_50plus_pct",   # Paying 50%+ (severely cost burdened)
    "B25003_001E": "housing_units_occupied",   # Total occupied housing units
    "B25003_003E": "renter_occupied",          # Renter-occupied units
    "B01003_001E": "population",               # Total population
    "B17001_002E": "poverty_count",            # Population below federal poverty line
}

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Extract ────────────────────────────────────────────────────────────────────

def fetch_census_housing(api_key: str) -> pd.DataFrame:
    """Fetch county-level housing burden variables from Census ACS 5-year estimates."""
    var_list = ["NAME"] + list(ACS_VARS.keys())
    params = {
        "get": ",".join(var_list),
        "for": "county:*",
        "in": "state:*",
        "key": api_key,
    }

    log.info("Census ACS → requesting %d variables for all U.S. counties...", len(ACS_VARS))
    resp = requests.get(CENSUS_ENDPOINT, params=params, timeout=60)
    resp.raise_for_status()

    try:
        rows = resp.json()
    except Exception:
        raise RuntimeError(f"Census API returned non-JSON response:\n{resp.text[:500]}")
    df = pd.DataFrame(rows[1:], columns=rows[0])

    df["fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
    df = df.rename(columns=ACS_VARS)

    numeric_cols = list(ACS_VARS.values())
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    # Derived rates — suppress divide-by-zero with pd.NA
    renter_base = df["renter_units_total"].replace(0, pd.NA)
    occupied_base = df["housing_units_occupied"].replace(0, pd.NA)
    pop_base = df["population"].replace(0, pd.NA)

    df["rent_burden_rate"] = (
        df[["rent_burden_30_35pct", "rent_burden_35_40pct",
            "rent_burden_40_50pct", "rent_burden_50plus_pct"]].sum(axis=1)
        / renter_base
    )
    df["severe_rent_burden_rate"] = df["rent_burden_50plus_pct"] / renter_base
    df["renter_rate"] = df["renter_occupied"] / occupied_base
    df["poverty_rate"] = df["poverty_count"] / pop_base

    keep = [
        "fips", "NAME", "state", "population",
        "renter_rate", "poverty_rate",
        "rent_burden_rate", "severe_rent_burden_rate",
        "renter_units_total", "housing_units_occupied",
    ]
    log.info("Census ACS → %d counties loaded", len(df))
    return df[keep].copy()


def fetch_vera_incarceration() -> pd.DataFrame:
    """
    Download Vera Institute incarceration trends CSV and return the most
    recent complete year of county-level data.
    """
    log.info("Vera Institute → downloading incarceration trends CSV...")
    resp = requests.get(VERA_URL, timeout=120)
    resp.raise_for_status()

    df = pd.read_csv(StringIO(resp.text), low_memory=False)

    df["fips"] = df["county_fips"].astype(str).str.zfill(5)

    # Pick the year with the most non-null jail rate values (avoids partial/projection years)
    coverage = df.groupby("year")["total_jail_pop_rate"].count()
    best_year = int(coverage.idxmax())
    df = df[df["year"] == best_year].copy()
    log.info("Vera Institute → using year=%d (%d counties, best coverage)", best_year, len(df))

    wanted = {
        "fips":                      "fips",
        "county_name":               "vera_county_name",
        "state_abbr":                "vera_state",
        "total_pop_15to64":          "vera_pop_15to64",
        "total_jail_pop_rate":       "jail_pop_rate_per100k",
        "total_prison_pop_rate":     "prison_pop_rate_per100k",
        "total_pretrial_custody_rate": "pretrial_jail_rate_per100k",
        "black_jail_pop_rate":       "black_jail_rate_per100k",
        "white_jail_pop_rate":       "white_jail_rate_per100k",
    }
    available = {k: v for k, v in wanted.items() if k in df.columns}
    missing = set(wanted) - set(available)
    if missing:
        log.warning("Vera columns not found (schema may have changed): %s", missing)

    return df[list(available.keys())].rename(columns=available).copy()

def fetch_cdc_places() -> pd.DataFrame:
    """
    Fetch county-level mental health and substance use data from CDC PLACES
    via the Socrata API. Returns one row per county with measures as columns.
    """
    log.info("CDC PLACES → fetching mental health and substance use data...")

    measure_ids = list(CDC_MEASURES.keys())
    where_clause = " OR ".join(f"measureid='{m}'" for m in measure_ids)

    params = {
        "$where":  f"datavaluetypeid='AgeAdjPrv' AND ({where_clause})",
        "$select": "locationid,measureid,data_value",
        "$limit":  "50000",
    }

    resp = requests.get(CDC_PLACES_URL, params=params, timeout=60)
    resp.raise_for_status()

    raw = pd.DataFrame(resp.json())
    if raw.empty:
        log.warning("CDC PLACES returned no data — skipping")
        return pd.DataFrame(columns=["fips"] + list(CDC_MEASURES.values()))

    raw["data_value"] = pd.to_numeric(raw["data_value"], errors="coerce") / 100
    raw["fips"] = raw["locationid"].astype(str).str.zfill(5)

    # Pivot from long (one row per measure) to wide (one row per county)
    wide = (
        raw.pivot_table(index="fips", columns="measureid", values="data_value", aggfunc="mean")
        .rename(columns=CDC_MEASURES)
        .reset_index()
    )
    # Keep only columns we asked for (pivot may include extras)
    keep = ["fips"] + [c for c in CDC_MEASURES.values() if c in wide.columns]
    wide = wide[keep]

    log.info("CDC PLACES → %d counties loaded (%d measures)", len(wide), len(keep) - 1)
    return wide

# ── Transform ──────────────────────────────────────────────────────────────────

def join_sources(
    housing: pd.DataFrame,
    incarceration: pd.DataFrame,
    health: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join all three sources on FIPS county codes (Census as base)."""
    log.info("Joining all sources on FIPS county codes...")
    merged = housing.merge(incarceration, on="fips", how="left")
    merged = merged.merge(health, on="fips", how="left")
    log.info("Joined → %d rows, %d columns", len(merged), len(merged.columns))
    return merged

# ── Load ───────────────────────────────────────────────────────────────────────

def write_outputs(merged: pd.DataFrame, report: dict) -> None:
    """Write the final CSV and validation report to output/."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    csv_path = OUTPUT_DIR / "housing_justice_county.csv"
    merged.to_csv(csv_path, index=False)
    log.info("CSV → %s (%d rows)", csv_path, len(merged))

    report_path = OUTPUT_DIR / "validation_report.txt"
    with open(report_path, "w") as f:
        f.write("Housing Justice Pipeline — Validation Report\n")
        f.write("=" * 48 + "\n\n")
        for key, value in report.items():
            f.write(f"{key}: {value}\n")
    log.info("Validation report → %s", report_path)

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not CENSUS_API_KEY:
        log.error("CENSUS_API_KEY not set — add it to .env or your environment")
        sys.exit(1)

    housing       = fetch_census_housing(CENSUS_API_KEY)
    incarceration = fetch_vera_incarceration()
    health        = fetch_cdc_places()
    merged        = join_sources(housing, incarceration, health)

    log.info("Running validation...")
    report = run_validation(housing, incarceration, merged)

    write_outputs(merged, report)

    print("\n── Pipeline complete ─────────────────────────────────────")
    print(f"  Counties in output : {report['joined_counties']}")
    print(f"  Vera join rate     : {report['join_rate_pct']}%")
    if "median_pop_discrepancy_pct" in report:
        print(f"  Pop cross-check    : {report['median_pop_discrepancy_pct']}% median discrepancy")
    print(f"  Output CSV         : {OUTPUT_DIR / 'housing_justice_county.csv'}")
    print(f"  Validation report  : {OUTPUT_DIR / 'validation_report.txt'}")


if __name__ == "__main__":
    main()
