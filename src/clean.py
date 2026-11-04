"""Clean the CSO NPO13 'Earnings of Employed Non-Progressors' table.

Input : the raw long-format CSV downloaded from data.gov.ie / CSO PxStat.
Output: data/processed/npo13_tidy.csv and .parquet - one row per cell
        (cohort x gender x NFQ x sector x outcome x years-since) with columns
        p25, p50, p75 (weekly earnings, nominal EUR), n (employed headcount) and
        p25_real, p50_real, p75_real (constant 2024 EUR, deflated by CSO CPA01 CPI
        for earnings_year = cohort_year + years_since).

Zero handling (the raw file uses 0 for three different things):
  * not_observed - cohort_year + years_since > LATEST_EARNINGS_YEAR, the
                   follow-up year hasn't happened yet  -> all values NaN
  * no_cases     - headcount is 0                       -> earnings NaN, n = 0
  * suppressed   - headcount > 0 but earnings 0 (small cells, CSO disclosure
                   control)                             -> earnings NaN
  * ok           - published values

Run:  python src/clean.py [path/to/raw.csv]
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cpi import BASE_YEAR, deflator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW_DEFAULT = ROOT / "NPO13_Earnings of Employed Non_progressors.csv"
RAW_URL = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/NPO13/CSV/1.0/en"
OUT_DIR = ROOT / "data" / "processed"

LATEST_EARNINGS_YEAR = 2024  # 2018 cohort + 6 years

STAT_MAP = {"NPO13C01": "p25", "NPO13C02": "p50", "NPO13C03": "p75", "NPO13C04": "n"}
DIM_MAP = {
    "Non-Progression Year": "cohort_year",
    "Gender": "gender",
    "NFQ Level": "nfq_level",
    "C03430V04137": "sector_code",
    "NACE Rev. 2 Sector of Employment": "sector",
    "Outcome": "outcome",
    "Years Since Non-Progression": "years_since_label",
}
EARN = ["p25", "p50", "p75"]


def load_raw(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"{path.name} not found - downloading from CSO")
        urllib.request.urlretrieve(RAW_URL, path)
    df = pd.read_csv(path, encoding="utf-8-sig")
    expected = set(STAT_MAP)
    found = set(df["STATISTIC"].unique())
    if found != expected:
        raise ValueError(f"Unexpected STATISTIC codes: {found ^ expected}")
    return df


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=DIM_MAP)
    df["stat"] = df["STATISTIC"].map(STAT_MAP)
    dims = list(DIM_MAP.values())
    wide = (
        df.pivot_table(index=dims, columns="stat", values="VALUE", aggfunc="first")
        .reset_index()
        .rename_axis(columns=None)
    )
    wide["years_since"] = wide["years_since_label"].str.extract(r"(\d+)").astype(int)
    wide = wide.drop(columns="years_since_label")
    wide["earnings_year"] = wide["cohort_year"] + wide["years_since"]

    # Tidy up labels
    wide["outcome"] = wide["outcome"].replace({"All Graduate Outcomes": "All outcomes"})
    wide["sector"] = wide["sector"].replace({"All NACE Economic Sector": "All sectors"})

    # Classify zeros
    not_obs = wide["earnings_year"] > LATEST_EARNINGS_YEAR
    no_cases = ~not_obs & (wide["n"] == 0)
    suppressed = ~not_obs & (wide["n"] > 0) & (wide["p50"] == 0)
    wide["status"] = np.select(
        [not_obs, no_cases, suppressed], ["not_observed", "no_cases", "suppressed"], "ok"
    )
    wide.loc[wide["status"] != "ok", EARN] = np.nan
    wide.loc[not_obs, "n"] = np.nan

    # Sanity checks
    ok = wide[wide["status"] == "ok"]
    assert (ok["p25"] <= ok["p50"]).all() and (ok["p50"] <= ok["p75"]).all(), "percentile order"
    assert (ok[EARN] > 0).all().all(), "zero earnings left in ok rows"

    wide["iqr"] = wide["p75"] - wide["p25"]

    # Real terms: constant euro of cpi.BASE_YEAR (CSO CPA01 annual average CPI)
    wide["deflator"] = np.nan
    obs = wide["status"] != "not_observed"
    wide.loc[obs, "deflator"] = deflator(wide.loc[obs, "earnings_year"])
    for c in EARN:
        wide[f"{c}_real"] = (wide[c] * wide["deflator"]).round(1)

    cols = ["cohort_year", "years_since", "earnings_year", "gender", "nfq_level",
            "sector_code", "sector", "outcome", "n", "p25", "p50", "p75", "iqr",
            "deflator", "p25_real", "p50_real", "p75_real", "status"]
    wide = wide[cols].sort_values(cols[:8]).reset_index(drop=True)
    for c in ["gender", "nfq_level", "sector", "sector_code", "outcome", "status"]:
        wide[c] = wide[c].astype("category")
    return wide


def main(raw: Path = RAW_DEFAULT) -> pd.DataFrame:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = tidy(load_raw(raw))
    out.to_parquet(OUT_DIR / "npo13_tidy.parquet", index=False)
    out.to_csv(OUT_DIR / "npo13_tidy.csv", index=False)
    print(f"{len(out):,} rows -> {OUT_DIR}")
    print(out["status"].value_counts().to_string())
    return out


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_DEFAULT)
