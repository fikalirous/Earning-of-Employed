"""CSO Consumer Price Index (table CPA01) - annual average, All items, base Dec 2023 = 100.

Used to deflate NPO13 nominal weekly earnings into constant euro of BASE_YEAR.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CPI_PATH = ROOT / "data" / "raw" / "cpi" / "CPA01.csv"
CPI_URL = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/CPA01/CSV/1.0/en"
CPI_STAT = "CPA01C06"  # Consumer Price Index (Base Dec 2023=100)
BASE_YEAR = 2024  # latest NPO13 earnings year


def download(path: Path = CPI_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(CPI_URL, path)
    return path


def load_cpi(path: Path = CPI_PATH) -> pd.Series:
    """Annual CPI index, indexed by year."""
    if not path.exists():
        download(path)
    d = pd.read_csv(path, encoding="utf-8-sig")
    d = d[(d["STATISTIC"] == CPI_STAT) & (d["Commodity Group"] == "All items")]
    s = d.set_index("Year")["VALUE"].astype(float).rename("cpi")
    if s.empty:
        raise ValueError(f"No {CPI_STAT} 'All items' rows in {path}")
    return s


def deflator(years, base_year: int = BASE_YEAR, cpi: pd.Series | None = None) -> pd.Series:
    """Multiplier that converts nominal euro of `years` into euro of `base_year`."""
    cpi = load_cpi() if cpi is None else cpi
    missing = set(pd.unique(years)) - set(cpi.index)
    if missing:
        raise ValueError(f"CPI missing for years {sorted(missing)}")
    return pd.Series(years).map(cpi[base_year] / cpi).to_numpy()
