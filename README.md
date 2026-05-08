# Housing Justice Pipeline

County-level data pipeline linking **housing cost burden** (U.S. Census ACS) with **incarceration trends** (Vera Institute) across all U.S. counties.

Built to support civic research on the structural relationship between housing instability and incarceration.

## Data Sources

| Source | Data | Geography | Vintage |
|--------|------|-----------|---------|
| [U.S. Census ACS 5-Year](https://api.census.gov/data/2022/acs/acs5) | Housing cost burden, renter rate, poverty rate | County (~3,100) | 2022 |
| [Vera Institute Incarceration Trends](https://github.com/vera-institute/incarceration-trends) | Jail population rate, prison admissions, pretrial detention, racial disparities | County | 2018 (latest available) |

**Join key:** 5-digit FIPS county code

## Setup

```bash
git clone <repo-url>
cd housing-justice-pipeline

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# open .env and paste your Census API key
```

Get a free Census API key (instant): https://api.census.gov/data/key_signup.html

## Usage

```bash
# Run the full data pipeline (requires Census API key in .env)
python pipeline.py

# Generate static charts (scatter plots, bar charts, clustering)
python visualize.py

# Generate choropleth maps (downloads Census shapefile on first run)
python choropleth.py
```

Output written to `output/` (gitignored):

```
output/
├── housing_justice_county.csv    # ~3,100 county rows
├── validation_report.txt         # cross-source validation summary
└── figures/
    ├── 01_scatter_burden_vs_jail.png
    ├── 02_top20_severe_rent_burden.png
    ├── 03_top20_jail_rate.png
    ├── 04_racial_disparity_ratio.png
    ├── 05_dual_burden_counties.png
    ├── 06_correlation_heatmap.png
    ├── 07_mental_health_vs_jail.png
    ├── 08_county_clusters.png
    ├── 09_choropleth_rent_burden.png       # GeoPandas choropleth
    ├── 10_choropleth_jail_rate.png         # GeoPandas choropleth
    ├── 11_choropleth_racial_disparity.png  # GeoPandas choropleth
    └── 12_choropleth_dual_burden.png       # GeoPandas choropleth
```

## Output Schema

| Column | Source | Description |
|--------|--------|-------------|
| `fips` | — | 5-digit FIPS county code |
| `NAME` | Census | County and state name |
| `population` | Census ACS | Total population |
| `renter_rate` | Census ACS | Share of occupied units that are renter-occupied |
| `poverty_rate` | Census ACS | Share of population below the federal poverty line |
| `rent_burden_rate` | Census ACS | Share of renters paying 30%+ of income on rent |
| `severe_rent_burden_rate` | Census ACS | Share of renters paying 50%+ of income on rent |
| `jail_pop_rate_per100k` | Vera | Jail population per 100,000 residents |
| `prison_admission_rate_per100k` | Vera | Prison admissions per 100,000 residents |
| `pretrial_jail_rate_per100k` | Vera | Pretrial detainees per 100,000 residents |
| `black_jail_rate_per100k` | Vera | Jail rate for Black residents per 100,000 |
| `white_jail_rate_per100k` | Vera | Jail rate for white residents per 100,000 |

## Validation

Four checks run before any output is written:

| Check | Type | Description |
|-------|------|-------------|
| Join coverage | Soft | % of Census counties matched to Vera data |
| Null rates | Soft | Per-column null %; logged in validation report |
| Population cross-check | Soft | Census vs Vera population figures; flags counties with >10% discrepancy |
| Range checks | **Hard** | Rate columns must be in [0, 1]; pipeline exits if violated |

## Project Structure

```
housing-justice-pipeline/
├── pipeline.py       # Extract → Transform → Load
├── validate.py       # Cross-source validation checks
├── visualize.py      # Static charts (scatter, bar, clustering)
├── choropleth.py     # GeoPandas choropleth maps (county-level)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Notes

- **Vintage gap:** Census data is 2022; Vera data is 2018. Population discrepancies between sources are expected and noted in the validation report.
- **Missing Vera counties:** ~15% of Census counties have no Vera match — typically small, rural counties below Vera's reporting threshold. These rows are retained with null incarceration columns.
- **Interpretation note:** Jail and prison rates reflect policing policy and systemic factors, not individual behavior. Do not use them as a proxy for crime rates.

## Data Licenses

- Census ACS: Public domain (U.S. government)
- Vera Institute Incarceration Trends: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
