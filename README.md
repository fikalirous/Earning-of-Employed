# Earnings of Employed Non-Progressors (CSO NPO13)

Analysis of weekly earnings of Irish higher-education first-year entrants who did **not progress** to second year and went into employment.

- **Source:** [data.gov.ie – NPO13](https://data.gov.ie/dataset/npo13-earnings-of-employed-non-progressors), Central Statistics Office, CC-BY-4.0
- **API (CSV):** https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/NPO13/CSV/1.0/en

## Layout

```
app.py                                           Streamlit dashboard
.streamlit/config.toml                           Streamlit theme/server settings
requirements.txt / requirements-dev.txt          app deps / + notebook deps
NPO13_Earnings of Employed Non_progressors.csv   raw download (untouched)
data/raw/cpi/CPA01.csv                           CSO annual CPI (auto-downloaded by src/cpi.py if missing)
src/clean.py                                     raw -> tidy (zeros classified, wide p25/p50/p75/n, real-terms columns)
src/cpi.py                                       CPI loader + deflator to 2024 euro
data/raw/heo/HEO12.csv                           CSO graduate earnings (auto-downloaded if missing)
src/graduates.py                                 HEO12 -> data/processed/heo12_tidy.{parquet,csv}, same zero rules + real terms
notebooks/02_vs_graduates.ipynb                  non-progressor vs graduate earnings, by NFQ level and gender
data/processed/npo13_tidy.{parquet,csv}          cleaned output, one row per cell
notebooks/01_eda.ipynb                           exploratory analysis
reports/figures/                                 charts exported by the notebook
```

## Dashboard (Streamlit)

```bash
pip install -r requirements.txt
streamlit run app.py
```

`app.py` has four tabs: Overview, Explore (gender / NFQ / outcome / sector), vs Graduates, Data (filter + CSV download).
Sidebar switches between real (2024 €) and nominal, and between median / P25 / P75.

**Deploy privately on Streamlit Community Cloud**
1. Sign in at share.streamlit.io with GitHub and allow access to private repositories.
2. *Create app* → repo `fikalirous/Earning-of-Employed`, branch `main`, main file `app.py`.
3. After deploy: *Settings → Sharing* → keep the app **private** and invite viewers by email.

## Notebooks

```bash
pip install -r requirements-dev.txt
python src/clean.py
python src/graduates.py
jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb
jupyter nbconvert --to notebook --execute --inplace notebooks/02_vs_graduates.ipynb
```

Only the small processed parquet files (`data/processed/*.parquet`, ~300 KB) are in git, so the dashboard
starts without downloading anything. Raw CSVs are not committed; the scripts download any missing raw table
(NPO13, HEO12, CPA01) from the CSO PxStat API and rebuild `data/processed/`.

## Tidy schema

| column | meaning |
|---|---|
| cohort_year | year of non-progression (2018–2023) |
| years_since | 1–6 years after non-progression |
| earnings_year | cohort_year + years_since |
| gender, nfq_level, sector, sector_code, outcome | dimensions ("All …" rows are totals) |
| n | employed headcount (rounded to 5) |
| p25, p50, p75, iqr | weekly earnings percentiles, nominal € (rounded to 5) |
| deflator, p25_real, p50_real, p75_real | CPI multiplier and percentiles in constant 2024 € (CSO CPA01 annual CPI, `src/cpi.py`) |
| status | `ok`, `suppressed` (n>0 but earnings withheld), `no_cases` (n=0), `not_observed` (follow-up year after 2024) |

The raw file uses `0` for all three non-`ok` cases. Treat them as missing, not as €0.
