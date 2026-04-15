"""
Housing Justice Pipeline — Visualizations

Reads output/housing_justice_county.csv and writes charts to output/figures/.

Usage:
  python visualize.py
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import numpy as np

# ── Config ─────────────────────────────────────────────────────────────────────

INPUT_PATH  = Path("output/housing_justice_county.csv")
FIGURES_DIR = Path("output/figures")

PALETTE     = "#2C3E50"
ACCENT      = "#E74C3C"
HIGHLIGHT   = "#E67E22"
GRAY        = "#BDC3C7"

plt.rcParams.update({
    "font.family":        "sans-serif",
    "font.size":          11,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "figure.dpi":         150,
    "figure.subplot.bottom": 0.18,  # reserve space below axes for source text
})

# ── Helpers ────────────────────────────────────────────────────────────────────

def save(fig: plt.Figure, name: str) -> None:
    path = FIGURES_DIR / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {path}")


def short_name(name: str) -> str:
    """'Autauga County, Alabama' → 'Autauga, AL'"""
    parts = name.split(", ")
    county = parts[0].replace(" County", "").replace(" Parish", "").replace(" Borough", "")
    state  = parts[1][:2].upper() if len(parts) > 1 else ""
    return f"{county}, {state}"

# ── Charts ─────────────────────────────────────────────────────────────────────

def chart_scatter(df: pd.DataFrame) -> None:
    """Rent burden rate vs jail rate, colored by poverty rate."""
    sub = df.dropna(subset=["rent_burden_rate", "jail_pop_rate_per100k", "poverty_rate"])
    # Cap jail rate for readability (top 1% are county-jail outliers)
    cap = sub["jail_pop_rate_per100k"].quantile(0.99)
    sub = sub[sub["jail_pop_rate_per100k"] <= cap].copy()

    # Counties to label
    label_counties = [
        "East Carroll Parish, Louisiana",
        "Jeff Davis County, Texas",
        "Gallatin County, Illinois",
        "Watauga County, North Carolina",
        "Catahoula Parish, Louisiana",
    ]

    fig, ax = plt.subplots(figsize=(10, 7))

    sc = ax.scatter(
        sub["rent_burden_rate"] * 100,
        sub["jail_pop_rate_per100k"],
        c=sub["poverty_rate"] * 100,
        cmap="YlOrRd",
        alpha=0.5,
        s=18,
        linewidths=0,
    )

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Poverty rate (%)", fontsize=10)

    # Label notable counties
    for _, row in sub[sub["NAME"].isin(label_counties)].iterrows():
        ax.annotate(
            short_name(row["NAME"]),
            xy=(row["rent_burden_rate"] * 100, row["jail_pop_rate_per100k"]),
            xytext=(8, 4),
            textcoords="offset points",
            fontsize=8,
            color=ACCENT,
            fontweight="bold",
        )
        ax.scatter(
            row["rent_burden_rate"] * 100,
            row["jail_pop_rate_per100k"],
            color=ACCENT, s=40, zorder=5,
        )

    ax.set_xlabel("Rent burden rate — share of renters paying 30%+ of income on rent (%)")
    ax.set_ylabel("Jail population rate (per 100,000 residents)")
    ax.set_title("Housing Cost Burden vs. Incarceration by U.S. County", fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.text(
        0.01, -0.18,
        "Sources: U.S. Census ACS 5-Year (2022), Vera Institute Incarceration Trends (2005). "
        "Top 1% jail-rate counties capped for readability.",
        transform=ax.transAxes, fontsize=7.5, color="gray",
    )

    save(fig, "01_scatter_burden_vs_jail.png")


def chart_top_burden(df: pd.DataFrame) -> None:
    """Top 20 counties by severe rent burden rate."""
    top = (
        df[["NAME", "severe_rent_burden_rate", "poverty_rate"]]
        .dropna()
        .sort_values("severe_rent_burden_rate", ascending=False)
        .head(20)
    )
    top["label"] = top["NAME"].apply(short_name)

    fig, ax = plt.subplots(figsize=(10, 7))
    colors = [ACCENT if v >= 0.40 else PALETTE for v in top["severe_rent_burden_rate"]]
    bars = ax.barh(top["label"][::-1], top["severe_rent_burden_rate"][::-1] * 100, color=colors[::-1])

    for bar, val in zip(bars, top["severe_rent_burden_rate"][::-1] * 100):
        ax.text(val + 0.4, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=9)

    ax.set_xlabel("Share of renters paying 50%+ of income on rent")
    ax.set_title("Top 20 Counties by Severe Rent Burden", fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.set_xlim(0, top["severe_rent_burden_rate"].max() * 100 + 10)
    ax.text(
        0.01, -0.18,
        "Source: U.S. Census ACS 5-Year (2022).",
        transform=ax.transAxes, fontsize=7.5, color="gray",
    )

    save(fig, "02_top20_severe_rent_burden.png")


def chart_top_jail(df: pd.DataFrame) -> None:
    """Top 20 counties by jail rate, excluding statistical outliers (large regional jails)."""
    top = (
        df[["NAME", "jail_pop_rate_per100k", "poverty_rate", "rent_burden_rate"]]
        .dropna()
        .sort_values("jail_pop_rate_per100k", ascending=False)
        .head(20)
    )
    top["label"] = top["NAME"].apply(short_name)

    fig, ax = plt.subplots(figsize=(10, 7))
    colors = [ACCENT if v >= 10000 else PALETTE for v in top["jail_pop_rate_per100k"]]
    bars = ax.barh(top["label"][::-1], top["jail_pop_rate_per100k"][::-1], color=colors[::-1])

    for bar, val in zip(bars, top["jail_pop_rate_per100k"][::-1]):
        ax.text(val + 50, bar.get_y() + bar.get_height() / 2,
                f"{val:,.0f}", va="center", fontsize=9)

    ax.set_xlabel("Jail population per 100,000 residents")
    ax.set_title("Top 20 Counties by Jail Population Rate", fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_xlim(0, top["jail_pop_rate_per100k"].max() * 1.18)
    ax.text(
        0.01, -0.18,
        "Note: Very high rates in small counties reflect regional jails whose population "
        "exceeds the local resident count. Source: Vera Institute (2005).",
        transform=ax.transAxes, fontsize=7.5, color="gray",
    )

    save(fig, "03_top20_jail_rate.png")


def chart_racial_disparity(df: pd.DataFrame) -> None:
    """Distribution of Black/white jail rate ratio across counties."""
    sub = df.dropna(subset=["black_jail_rate_per100k", "white_jail_rate_per100k"]).copy()
    sub = sub[sub["white_jail_rate_per100k"] > 0].copy()
    sub["ratio"] = sub["black_jail_rate_per100k"] / sub["white_jail_rate_per100k"]

    # Cap at 30x for histogram readability
    cap = 30
    capped = sub[sub["ratio"] <= cap]["ratio"]
    n_above = (sub["ratio"] > cap).sum()

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(capped, bins=60, color=PALETTE, alpha=0.85, edgecolor="white", linewidth=0.3)

    median_val = sub["ratio"].median()
    ax.axvline(median_val, color=ACCENT, linewidth=1.8, linestyle="--")
    ax.text(median_val + 0.3, ax.get_ylim()[1] * 0.92,
            f"Median: {median_val:.1f}x", color=ACCENT, fontsize=10, fontweight="bold")

    ax.axvline(1, color=GRAY, linewidth=1.2, linestyle=":")
    ax.text(1.2, ax.get_ylim()[1] * 0.80, "Parity (1x)", color="gray", fontsize=9)

    ax.set_xlabel("Black jail rate ÷ white jail rate (ratio)")
    ax.set_ylabel("Number of counties")
    ax.set_title("Racial Disparity in Jail Rates Across U.S. Counties\n(Black vs. White residents)",
                 fontweight="bold", pad=14)
    ax.text(
        0.01, -0.18,
        f"Counties shown: {len(capped):,}. {n_above} counties with ratio >30x not shown. "
        "Source: Vera Institute (2005).",
        transform=ax.transAxes, fontsize=7.5, color="gray",
    )

    save(fig, "04_racial_disparity_ratio.png")


def chart_dual_burden(df: pd.DataFrame) -> None:
    """Counties appearing in both top-quintile rent burden and top-quintile jail rate."""
    sub = df.dropna(subset=["severe_rent_burden_rate", "jail_pop_rate_per100k"]).copy()

    burden_thresh = sub["severe_rent_burden_rate"].quantile(0.80)
    jail_thresh   = sub["jail_pop_rate_per100k"].quantile(0.80)

    sub["high_burden"] = sub["severe_rent_burden_rate"] >= burden_thresh
    sub["high_jail"]   = sub["jail_pop_rate_per100k"]   >= jail_thresh
    sub["dual"]        = sub["high_burden"] & sub["high_jail"]

    cap = sub["jail_pop_rate_per100k"].quantile(0.99)
    plot = sub[sub["jail_pop_rate_per100k"] <= cap].copy()

    fig, ax = plt.subplots(figsize=(10, 7))

    # Background points
    ax.scatter(
        plot.loc[~plot["dual"], "severe_rent_burden_rate"] * 100,
        plot.loc[~plot["dual"], "jail_pop_rate_per100k"],
        color=GRAY, alpha=0.4, s=14, linewidths=0, label="Other counties",
    )

    # Dual-burden counties
    dual = plot[plot["dual"]]
    ax.scatter(
        dual["severe_rent_burden_rate"] * 100,
        dual["jail_pop_rate_per100k"],
        color=ACCENT, alpha=0.85, s=30, linewidths=0,
        label=f"High burden + high incarceration (n={sub['dual'].sum()})",
        zorder=4,
    )

    # Label top 8 dual-burden
    for _, row in dual.nlargest(8, "jail_pop_rate_per100k").iterrows():
        ax.annotate(
            short_name(row["NAME"]),
            xy=(row["severe_rent_burden_rate"] * 100, row["jail_pop_rate_per100k"]),
            xytext=(6, 3), textcoords="offset points",
            fontsize=7.5, color=ACCENT, fontweight="bold",
        )

    # Threshold lines
    ax.axvline(burden_thresh * 100, color=HIGHLIGHT, linewidth=1, linestyle="--", alpha=0.7)
    ax.axhline(jail_thresh,         color=HIGHLIGHT, linewidth=1, linestyle="--", alpha=0.7)

    ax.set_xlabel("Severe rent burden rate — share paying 50%+ of income on rent (%)")
    ax.set_ylabel("Jail population rate (per 100,000 residents)")
    ax.set_title("Counties with Both High Housing Burden and High Incarceration",
                 fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend(loc="upper left", fontsize=9, framealpha=0.6)
    ax.text(
        0.01, -0.18,
        "Dashed lines mark 80th percentile thresholds for each dimension. "
        "Top 1% jail-rate counties capped. Sources: Census ACS (2022), Vera Institute (2005).",
        transform=ax.transAxes, fontsize=7.5, color="gray",
    )

    save(fig, "05_dual_burden_counties.png")

def chart_correlation_heatmap(df: pd.DataFrame) -> None:
    """Correlation heatmap across housing, incarceration, and health variables."""
    cols = {
        "poverty_rate":               "Poverty rate",
        "rent_burden_rate":           "Rent burden (30%+)",
        "severe_rent_burden_rate":    "Severe rent burden (50%+)",
        "renter_rate":                "Renter rate",
        "jail_pop_rate_per100k":      "Jail rate per 100k",
        "prison_pop_rate_per100k":    "Prison rate per 100k",
        "black_jail_rate_per100k":    "Black jail rate per 100k",
        "mental_health_distress_pct": "Mental health distress",
        "depression_pct":             "Depression prevalence",
        "binge_drinking_pct":         "Binge drinking",
        "current_smoking_pct":        "Current smoking",
    }
    available = {k: v for k, v in cols.items() if k in df.columns}
    sub = df[list(available.keys())].dropna(how="all").rename(columns=available)

    corr = sub.corr(method="spearman")

    fig, ax = plt.subplots(figsize=(11, 9))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)  # show lower triangle + diagonal

    sns.heatmap(
        corr,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        center=0,
        vmin=-1, vmax=1,
        linewidths=0.4,
        linecolor="#f0f0f0",
        ax=ax,
        annot_kws={"size": 8},
        cbar_kws={"shrink": 0.8, "label": "Spearman r"},
    )

    ax.set_title(
        "Spearman Correlations: Housing, Incarceration & Health by U.S. County",
        fontweight="bold", pad=16,
    )
    ax.tick_params(axis="x", rotation=40, labelsize=9)
    ax.tick_params(axis="y", rotation=0,  labelsize=9)
    ax.text(
        0.01, -0.20,
        "Sources: Census ACS (2022), Vera Institute (2005), CDC PLACES (2023). "
        "Spearman rank correlation. N varies by column availability.",
        transform=ax.transAxes, fontsize=7.5, color="gray",
    )

    save(fig, "06_correlation_heatmap.png")


def chart_health_vs_incarceration(df: pd.DataFrame) -> None:
    """Mental health distress and depression rates vs jail rate."""
    needed = ["mental_health_distress_pct", "depression_pct", "jail_pop_rate_per100k", "poverty_rate"]
    if not all(c in df.columns for c in needed):
        print("  skipping chart_health_vs_incarceration — CDC PLACES columns missing")
        return

    sub = df.dropna(subset=needed).copy()
    cap = sub["jail_pop_rate_per100k"].quantile(0.99)
    sub = sub[sub["jail_pop_rate_per100k"] <= cap]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    for ax, col, label in zip(
        axes,
        ["mental_health_distress_pct", "depression_pct"],
        ["Mental health distress\n(% with 14+ bad mental health days/month)", "Depression prevalence (%)"],
    ):
        sc = ax.scatter(
            sub[col] * 100,
            sub["jail_pop_rate_per100k"],
            c=sub["poverty_rate"] * 100,
            cmap="YlOrRd",
            alpha=0.45, s=16, linewidths=0,
        )
        # Trend line
        x = sub[col].dropna() * 100
        y = sub.loc[x.index, "jail_pop_rate_per100k"]
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        xs = np.linspace(x.min(), x.max(), 100)
        ax.plot(xs, p(xs), color=ACCENT, linewidth=1.6, linestyle="--", alpha=0.8)

        ax.set_xlabel(label)
        ax.set_title(f"{label.split(chr(10))[0]} vs Jail Rate", fontweight="bold")
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))

    axes[0].set_ylabel("Jail population rate (per 100,000 residents)")
    cbar = fig.colorbar(sc, ax=axes, pad=0.02)
    cbar.set_label("Poverty rate (%)", fontsize=10)

    fig.suptitle("Mental Health Burden vs. Incarceration Rate by U.S. County",
                 fontweight="bold", fontsize=13, y=1.01)
    axes[0].text(
        0.01, -0.20,
        "Sources: CDC PLACES (2023), Vera Institute (2005). "
        "Dashed line = linear trend. Top 1% jail-rate counties capped.",
        transform=axes[0].transAxes, fontsize=7.5, color="gray",
    )

    save(fig, "07_mental_health_vs_jail.png")


def chart_county_clusters(df: pd.DataFrame) -> None:
    """K-means clustering of counties on 5 structural dimensions."""
    try:
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
    except ImportError:
        print("  skipping clustering — run: pip install scikit-learn")
        return

    features = [
        "poverty_rate",
        "severe_rent_burden_rate",
        "jail_pop_rate_per100k",
        "mental_health_distress_pct",
        "binge_drinking_pct",
    ]
    available = [f for f in features if f in df.columns]
    sub = df.dropna(subset=available).copy()

    scaler = StandardScaler()
    X = scaler.fit_transform(sub[available])

    k = 5
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    sub["cluster"] = km.fit_predict(X)

    # Label clusters by their dominant characteristic
    cluster_means = sub.groupby("cluster")[available].mean()
    labels = []
    for i in range(k):
        row = cluster_means.loc[i]
        if "jail_pop_rate_per100k" in row and row["jail_pop_rate_per100k"] == cluster_means["jail_pop_rate_per100k"].max():
            labels.append("High incarceration")
        elif "severe_rent_burden_rate" in row and row["severe_rent_burden_rate"] == cluster_means["severe_rent_burden_rate"].max():
            labels.append("High housing burden")
        elif "mental_health_distress_pct" in row and row["mental_health_distress_pct"] == cluster_means["mental_health_distress_pct"].max():
            labels.append("High mental health distress")
        elif "poverty_rate" in row and row["poverty_rate"] == cluster_means["poverty_rate"].max():
            labels.append("High poverty")
        else:
            labels.append("Lower burden")
    sub["cluster_label"] = sub["cluster"].map(dict(enumerate(labels)))

    cluster_colors = ["#2C3E50", "#E74C3C", "#E67E22", "#27AE60", "#8E44AD"]
    color_map = dict(zip(sorted(sub["cluster_label"].unique()), cluster_colors))

    fig, ax = plt.subplots(figsize=(11, 7))

    cap = sub["jail_pop_rate_per100k"].quantile(0.99)
    plot = sub[sub["jail_pop_rate_per100k"] <= cap]

    for label, grp in plot.groupby("cluster_label"):
        ax.scatter(
            grp["severe_rent_burden_rate"] * 100,
            grp["jail_pop_rate_per100k"],
            label=f"{label} (n={len(grp)})",
            color=color_map.get(label, GRAY),
            alpha=0.55, s=18, linewidths=0,
        )

    ax.set_xlabel("Severe rent burden rate — share paying 50%+ of income on rent (%)")
    ax.set_ylabel("Jail population rate (per 100,000 residents)")
    ax.set_title(
        f"County Typology: {k} Clusters Across Housing, Incarceration & Health",
        fontweight="bold", pad=14,
    )
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend(loc="upper right", fontsize=9, framealpha=0.7)
    ax.text(
        0.01, -0.18,
        f"K-means (k={k}) on: {', '.join(available)}. Features standardized before clustering. "
        "Top 1% jail-rate counties capped. Sources: Census ACS (2022), Vera (2005), CDC PLACES (2023).",
        transform=ax.transAxes, fontsize=7.5, color="gray",
    )

    save(fig, "08_county_clusters.png")

    # Also print cluster summary
    print("\n  Cluster summary:")
    summary = sub.groupby("cluster_label")[available].mean()
    for col in available:
        if "pct" in col or "rate" in col and summary[col].max() < 2:
            summary[col] = (summary[col] * 100).round(1).astype(str) + "%"
        else:
            summary[col] = summary[col].round(1)
    print(summary.to_string())


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not INPUT_PATH.exists():
        print(f"Error: {INPUT_PATH} not found. Run pipeline.py first.")
        return

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_PATH)
    print(f"Loaded {len(df)} counties, {len(df.columns)} columns\n")

    print("Generating charts...")
    chart_scatter(df)
    chart_top_burden(df)
    chart_top_jail(df)
    chart_racial_disparity(df)
    chart_dual_burden(df)
    chart_correlation_heatmap(df)
    chart_health_vs_incarceration(df)
    chart_county_clusters(df)

    print(f"\nAll charts saved to {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
