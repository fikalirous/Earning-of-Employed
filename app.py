"""Streamlit dashboard: Earnings of Employed Non-Progressors (CSO NPO13) vs graduates (HEO12).

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
PROC = ROOT / "data" / "processed"

st.set_page_config(page_title="Non-Progressor Earnings", page_icon="📈", layout="wide")

# ---------------------------------------------------------------- palette
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
COHORT_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
GENDER_COL = {"Male": SERIES[0], "Female": SERIES[1], "Other gender": SERIES[2], "All genders": "#52514e"}
NFQ_COL = {"NFQ Level 6": SERIES[0], "NFQ Level 7": SERIES[1], "NFQ Level 8": SERIES[2], "All NFQ Levels": "#52514e"}
OUTCOME_COL = {"Employment only": SERIES[1], "Employment and Education": SERIES[0], "All outcomes": "#52514e"}
GRID = "rgba(128,128,128,0.18)"
LEVELS = ["NFQ Level 6", "NFQ Level 7", "NFQ Level 8"]
COURSE_YEARS = {"NFQ Level 6": 2, "NFQ Level 7": 3, "NFQ Level 8": 4}
ALL = dict(gender="All genders", nfq_level="All NFQ Levels", sector="All sectors", outcome="All outcomes")


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading data…")
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not (PROC / "npo13_tidy.parquet").exists():
        import clean
        clean.main()
    if not (PROC / "heo12_tidy.parquet").exists():
        import graduates
        graduates.main()
    npo = pd.read_parquet(PROC / "npo13_tidy.parquet")
    heo = pd.read_parquet(PROC / "heo12_tidy.parquet")
    for d in (npo, heo):
        for c in d.select_dtypes("category"):
            d[c] = d[c].astype(str)
    return npo, heo


npo, heo = load()


def sel(df: pd.DataFrame, **kw) -> pd.DataFrame:
    base = {k: v for k, v in ALL.items() if k in df.columns}
    base.update(kw)
    m = pd.Series(True, index=df.index)
    for k, v in base.items():
        if v is None:
            continue
        m &= df[k].isin(v) if isinstance(v, (list, tuple)) else (df[k] == v)
    return df[m]


def fig_base(title: str, y_title: str = "", pct: bool = False, height: int = 420) -> go.Figure:
    f = go.Figure()
    f.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=16)),
        height=height, margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
        xaxis=dict(showgrid=False, dtick=1),
        yaxis=dict(title=y_title, gridcolor=GRID, zeroline=False,
                   tickformat=".0%" if pct else ",.0f", tickprefix="" if pct else "€"),
    )
    return f


def line(f: go.Figure, x, y, name: str, color: str, hover_fmt: str = "€%{y:,.0f}") -> None:
    f.add_trace(go.Scatter(x=x, y=y, name=name, mode="lines+markers",
                           line=dict(color=color, width=2), marker=dict(size=8),
                           hovertemplate=f"{name}: {hover_fmt}<extra></extra>"))


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    basis = st.radio("Earnings basis", ["Real (2024 €)", "Nominal €"], index=0,
                     help="Real = deflated with CSO CPI (table CPA01) to 2024 prices.")
    stat_label = st.radio("Statistic", ["Median", "25th percentile", "75th percentile"], index=0)
    stat = {"Median": "p50", "25th percentile": "p25", "75th percentile": "p75"}[stat_label]
    VAL = f"{stat}_real" if basis.startswith("Real") else stat
    unit = "2024 €" if basis.startswith("Real") else "nominal €"
    st.divider()
    st.caption(
        "Source: CSO tables **NPO13** (non-progressors), **HEO12** (graduates), **CPA01** (CPI), "
        "via data.gov.ie, CC-BY-4.0. Weekly earnings, rounded to €5. Blank = not yet observed or suppressed."
    )

st.title("Earnings of Employed Non-Progressors")
st.markdown(
    "Weekly earnings of first-year entrants to Irish higher education who did **not progress** to second year "
    "and went into employment, followed up to six years — and how they compare with graduates."
)

tab_over, tab_explore, tab_grad, tab_data = st.tabs(["Overview", "Explore", "vs Graduates", "Data"])

# ---------------------------------------------------------------- overview
with tab_over:
    head = sel(npo)
    y1 = head[head.years_since == 1].set_index("cohort_year")
    c2018 = head[head.cohort_year == 2018].set_index("years_since")
    m8 = (sel(npo, nfq_level="NFQ Level 8", years_since=1, cohort_year=2022)[VAL].iloc[0] /
          sel(heo, nfq_level="NFQ Level 8", field="All fields of education", years_since=1, grad_year=2022)[VAL].iloc[0])

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric(f"Year-1 {stat_label.lower()}, 2023 cohort", f"€{y1.loc[2023, VAL]:,.0f}")
        d18 = y1.loc[2023, VAL] - y1.loc[2018, VAL]
        st.caption(f"{unit} · {'+' if d18 >= 0 else '−'}€{abs(d18):,.0f} vs 2018 cohort")
    with k2:
        st.metric("2018 cohort after 6 years", f"€{c2018.loc[6, VAL]:,.0f}")
        st.caption(f"{unit} · {c2018.loc[6, VAL] / c2018.loc[1, VAL] - 1:+.0%} since year 1")
    with k3:
        st.metric("Employed, 2023 cohort", f"{y1.loc[2023, 'n']:,.0f}")
        st.caption("people, year 1")
    with k4:
        st.metric("Level 8 vs graduates", f"{m8:.0%}")
        st.caption("of graduate pay, year 1 (2023)")

    traj = head.pivot_table(index="years_since", columns="cohort_year", values=VAL)
    f = fig_base(f"{stat_label} weekly earnings by cohort ({unit})")
    for i, c in enumerate(traj.columns):
        s = traj[c].dropna()
        line(f, s.index, s.values, str(c), COHORT_RAMP[i])
    f.update_xaxes(title="Years since non-progression")
    st.plotly_chart(f, width="stretch")
    st.caption("Older cohorts are lighter. In real terms, year-1 pay is roughly flat across cohorts; "
               "the nominal rise is mostly inflation (switch the basis in the sidebar).")

# ---------------------------------------------------------------- explore
with tab_explore:
    c1, c2, c3 = st.columns([1.2, 1, 1])
    dim_label = c1.selectbox("Break down by", ["Gender", "NFQ level", "Outcome", "Sector"])
    cohort = c2.selectbox("Cohort (non-progression year)", sorted(npo.cohort_year.unique()), index=0)
    dim = {"Gender": "gender", "NFQ level": "nfq_level", "Outcome": "outcome", "Sector": "sector"}[dim_label]

    # Fix every other dimension at its "All" value, except allow one extra filter
    others = [d for d in ["gender", "nfq_level", "outcome"] if d != dim]
    fixed = {}
    with c3:
        flt_dim = st.selectbox("Also filter", ["(none)"] + [d.replace("_", " ").title() for d in others])
    if flt_dim != "(none)":
        key = flt_dim.lower().replace(" ", "_")
        fixed[key] = st.selectbox(flt_dim, sorted(npo[key].unique()),
                                  index=sorted(npo[key].unique()).index(ALL[key]))

    d = sel(npo, cohort_year=cohort, **{dim: None}, **fixed)
    d = d[d[dim] != ALL[dim]] if dim != "sector" else d[~d.sector.isin(["All sectors", "Unknown"])]

    if dim == "sector":
        yrs = sorted(d.dropna(subset=[VAL]).years_since.unique())
        yr = st.select_slider("Years since non-progression", options=yrs, value=yrs[-1] if yrs else 1)
        s = d[d.years_since == yr].dropna(subset=[VAL]).sort_values(VAL)
        f = fig_base(f"{cohort} cohort, year {yr}: {stat_label.lower()} by sector ({unit})", height=560)
        f.add_trace(go.Bar(x=s[VAL], y=s.sector.str.replace(r" \(.*\)$", "", regex=True), orientation="h",
                           marker=dict(color=SERIES[0], cornerradius=4),
                           customdata=s[["n"]], text=s[VAL].map("€{:,.0f}".format), textposition="outside",
                           hovertemplate="%{y}<br>€%{x:,.0f}<br>n = %{customdata[0]:,.0f}<extra></extra>"))
        f.update_layout(hovermode="closest", showlegend=False)
        f.update_xaxes(tickprefix="€", gridcolor=GRID, dtick=None)
        f.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(f, width="stretch")
    else:
        cmap = {"gender": GENDER_COL, "nfq_level": NFQ_COL, "outcome": OUTCOME_COL}[dim]
        p = d.pivot_table(index="years_since", columns=dim, values=VAL)
        f = fig_base(f"{cohort} cohort: {stat_label.lower()} by {dim_label.lower()} ({unit})")
        for c in [k for k in cmap if k in p.columns]:
            s = p[c].dropna()
            if len(s):
                line(f, s.index, s.values, c, cmap[c])
        f.update_xaxes(title="Years since non-progression")
        st.plotly_chart(f, width="stretch")

    with st.expander("Table"):
        t = d.pivot_table(index=dim, columns="years_since", values=VAL).round(0)
        st.dataframe(t, width="stretch")

# ---------------------------------------------------------------- vs graduates
with tab_grad:
    st.markdown(
        "Matched on **calendar earnings year** and **years since leaving / graduating**, level by level "
        "(HEO12 *All NFQ Levels* includes Levels 9–10, so it isn't compared). Descriptive, not causal."
    )
    g1, g2 = st.columns(2)
    gender = g1.selectbox("Gender", ["All genders", "Female", "Male"])
    align = g2.radio("Align by", ["Years since leaving", "Years since starting college"], horizontal=True,
                     help="Starting-college view shifts graduates by course length − 1 "
                          "(L6 = 2, L7 = 3, L8 = 4 years, typical values).")

    KEY = ["earnings_year", "years_since", "gender", "nfq_level"]
    a = npo[(npo.sector == "All sectors") & (npo.outcome == "All outcomes") & (npo.status == "ok")
            & (npo.gender == gender) & npo.nfq_level.isin(LEVELS)][KEY + ["n", VAL]]
    b = heo[(heo.field == "All fields of education") & (heo.status == "ok")
            & (heo.gender == gender) & heo.nfq_level.isin(LEVELS)][KEY + ["n", VAL]]

    if align == "Years since leaving":
        mm = a.merge(b, on=KEY, suffixes=("_np", "_gr"))
        xcol, xtitle = "years_since", "Years since leaving / graduating"
    else:
        a = a.assign(x=a.years_since + 1)
        b = b.assign(x=b.years_since + b.nfq_level.map(COURSE_YEARS))
        mm = a.merge(b, on=["earnings_year", "x", "gender", "nfq_level"], suffixes=("_np", "_gr"))
        xcol, xtitle = "x", "Years since entering college"
    mm["ratio"] = mm[f"{VAL}_np"] / mm[f"{VAL}_gr"]

    r = mm.groupby(["nfq_level", xcol]).ratio.mean().unstack(0)
    f = fig_base("Non-progressor pay as % of graduate pay (average over 2019–2023)", pct=True)
    for lv in LEVELS:
        if lv in r:
            s = r[lv].dropna()
            line(f, s.index, s.values, lv.replace("NFQ ", ""), NFQ_COL[lv], hover_fmt="%{y:.0%}")
    f.add_hline(y=1, line=dict(color="#888", width=1, dash="dot"), annotation_text="parity",
                annotation_position="top left")
    f.update_xaxes(title=xtitle)
    st.plotly_chart(f, width="stretch")

    ey = st.select_slider("Earnings year", options=sorted(mm.earnings_year.unique()),
                          value=int(mm.earnings_year.max()))
    cols = st.columns(3)
    for col, lv in zip(cols, LEVELS):
        s = mm[(mm.nfq_level == lv) & (mm.earnings_year == ey)].sort_values(xcol)
        f = fig_base(lv.replace("NFQ ", ""), height=330)
        line(f, s[xcol], s[f"{VAL}_gr"], "Graduates", SERIES[0])
        line(f, s[xcol], s[f"{VAL}_np"], "Non-progressors", SERIES[1])
        f.update_xaxes(title=xtitle)
        col.plotly_chart(f, width="stretch")
    st.caption(f"{stat_label} weekly earnings in {ey} ({unit}).")

# ---------------------------------------------------------------- data
with tab_data:
    which = st.radio("Table", ["Non-progressors (NPO13)", "Graduates (HEO12)"], horizontal=True)
    df = npo if which.startswith("Non") else heo
    show_all = st.checkbox("Include not-observed / suppressed / empty rows", value=False)
    out = df if show_all else df[df.status == "ok"]
    st.caption(f"{len(out):,} rows. `status`: ok · suppressed (n > 0 but earnings withheld) · "
               "no_cases (n = 0) · not_observed (follow-up year not reached).")
    st.dataframe(out, width="stretch", height=420)
    st.download_button("Download CSV", out.to_csv(index=False).encode("utf-8"),
                       file_name=f"{'npo13' if which.startswith('Non') else 'heo12'}_tidy.csv", mime="text/csv")
