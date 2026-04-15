"""
Validation checks for the housing-justice pipeline.

run_validation() is called after the join and before writing output.
It returns a dict of findings for the validation report and raises
ValueError on hard failures (out-of-range rates).
"""

import pandas as pd


def _null_rate(series: pd.Series) -> float:
    return round(series.isna().mean() * 100, 1)


def run_validation(
    housing: pd.DataFrame,
    incarceration: pd.DataFrame,
    merged: pd.DataFrame,
) -> dict:
    """
    Cross-source validation checks.

    Soft checks: recorded in the report dict.
    Hard checks: raise ValueError immediately (pipeline should not write bad data).
    """
    report: dict = {}

    # ── 1. Join coverage ────────────────────────────────────────────────────
    report["census_counties"]    = len(housing)
    report["vera_counties"]      = len(incarceration)
    report["joined_counties"]    = len(merged)
    report["join_rate_pct"]      = round(len(merged) / len(housing) * 100, 1)

    unmatched = merged["jail_pop_rate_per100k"].isna().sum() if "jail_pop_rate_per100k" in merged.columns else "n/a"
    report["unmatched_census_counties"] = unmatched

    # ── 2. Null rates per key column ────────────────────────────────────────
    key_cols = [
        "rent_burden_rate",
        "severe_rent_burden_rate",
        "poverty_rate",
        "jail_pop_rate_per100k",
        "prison_admission_rate_per100k",
    ]
    for col in key_cols:
        if col in merged.columns:
            report[f"null_pct_{col}"] = _null_rate(merged[col])

    # ── 3. Vera coverage note (no total pop cross-check; Vera uses 15-64 age band) ──
    if "vera_pop_15to64" in merged.columns:
        matched = merged["vera_pop_15to64"].notna().sum()
        report["pop_crosscheck_counties"] = int(matched)
        report["pop_crosscheck_note"] = (
            "Vera reports population aged 15-64 only; direct Census total-pop "
            "cross-check not applicable. Coverage count above reflects matched counties."
        )

    # ── 4. Range checks — hard failure ──────────────────────────────────────
    rate_cols = ["rent_burden_rate", "severe_rent_burden_rate", "renter_rate", "poverty_rate"]
    for col in rate_cols:
        if col not in merged.columns:
            continue
        valid = merged[col].dropna()
        out_of_range = int(((valid < 0) | (valid > 1)).sum())
        report[f"out_of_range_{col}"] = out_of_range
        if out_of_range > 0:
            raise ValueError(
                f"Hard validation failure: {out_of_range} rows in '{col}' fall outside [0, 1]. "
                "Check Census variable denominators or raw API response."
            )

    # ── 5. Duplicate FIPS ───────────────────────────────────────────────────
    dupes = int(merged["fips"].duplicated().sum())
    report["duplicate_fips_rows"] = dupes
    if dupes > 0:
        report["duplicate_fips_warning"] = (
            f"WARNING: {dupes} duplicate FIPS rows in merged output. "
            "Check for many-to-one join artifact."
        )

    return report
