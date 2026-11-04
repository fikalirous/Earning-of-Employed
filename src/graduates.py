"""Clean CSO HEO12 'Graduate Earnings' into the same tidy shape as NPO13.

Output: data/processed/heo12_tidy.{parquet,csv}, one row per
grad_year x gender x field x NFQ x years_since, with p25/p50/p75 (nominal and
constant-2024 EUR) and n. Zero handling mirrors clean.py:
  not_observed (grad_year + years_since after the latest year with data),
  no_cases (n == 0), suppressed (n > 0 but earnings 0), ok.

Run:  python src/graduates.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cpi import deflator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "heo" / "HEO12.csv"
URL = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/HEO12/CSV/1.0/en"
OUT_DIR = ROOT / "data" / "processed"

STAT_MAP = {"HEO12C01": "n", "HEO12C02": "p25", "HEO12C03": "p50", "HEO12C04": "p75"}
DIM_MAP = {"Graduation Year": "grad_year", "Gender": "gender", "Field of Study": "field",
           "NFQ Level": "nfq_level", "Years Since Graduation": "years_since"}
EARN = ["p25", "p50", "p75"]


def load_raw(path: Path = RAW) -> pd.DataFrame:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, path)
    df = pd.read_csv(path, encoding="utf-8-sig")
    if set(df["STATISTIC"].unique()) != set(STAT_MAP):
        raise ValueError("Unexpected STATISTIC codes in HEO12")
    return df


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=DIM_MAP)
    df["stat"] = df["STATISTIC"].map(STAT_MAP)
    dims = list(DIM_MAP.values())
    w = (df.pivot_table(index=dims, columns="stat", values="VALUE", aggfunc="first")
           .reset_index().rename_axis(columns=None))
    w["earnings_year"] = w["grad_year"] + w["years_since"]

    latest = int(w.loc[w["n"] > 0, "earnings_year"].max())
    not_obs = w["earnings_year"] > latest
    no_cases = ~not_obs & (w["n"] == 0)
    suppressed = ~not_obs & (w["n"] > 0) & (w["p50"] == 0)
    w["status"] = np.select([not_obs, no_cases, suppressed],
                            ["not_observed", "no_cases", "suppressed"], "ok")
    w.loc[w["status"] != "ok", EARN] = np.nan
    w.loc[not_obs, "n"] = np.nan

    ok = w[w["status"] == "ok"]
    assert (ok["p25"] <= ok["p50"]).all() and (ok["p50"] <= ok["p75"]).all(), "percentile order"

    # CPI only covers years in CPA01; graduate data starts in 2011
    w["deflator"] = np.nan
    obs = w["status"] != "not_observed"
    w.loc[obs, "deflator"] = deflator(w.loc[obs, "earnings_year"])
    for c in EARN:
        w[f"{c}_real"] = (w[c] * w["deflator"]).round(1)

    cols = ["grad_year", "years_since", "earnings_year", "gender", "field", "nfq_level",
            "n", "p25", "p50", "p75", "deflator", "p25_real", "p50_real", "p75_real", "status"]
    w = w[cols].sort_values(cols[:6]).reset_index(drop=True)
    for c in ["gender", "field", "nfq_level", "status"]:
        w[c] = w[c].astype("category")
    w.attrs["latest_earnings_year"] = latest
    return w


def main() -> pd.DataFrame:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = tidy(load_raw())
    out.to_parquet(OUT_DIR / "heo12_tidy.parquet", index=False)
    out.to_csv(OUT_DIR / "heo12_tidy.csv", index=False)
    print(f"{len(out):,} rows -> {OUT_DIR} (latest earnings year {out.attrs['latest_earnings_year']})")
    print(out["status"].value_counts().to_string())
    return out


if __name__ == "__main__":
    main()
