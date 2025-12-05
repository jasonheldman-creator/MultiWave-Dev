import streamlit as st
import pandas as pd
from pathlib import Path

# -------------------------------------------------------------------
# CONFIG – matches your GitHub repo file names exactly
# -------------------------------------------------------------------
UNIVERSE_FILE = "Master_Stock_Sheet - Sheet5.csv"
WEIGHTS_FILE = "wave_weights.csv"

st.set_page_config(
    page_title="WAVES INTELLIGENCE – MULTIWAVE CONSOLE",
    layout="wide",
)


# -------------------------------------------------------------------
# DATA LOADERS
# -------------------------------------------------------------------
@st.cache_data
def load_universe(path: str) -> pd.DataFrame:
    """Load the master stock universe (Sheet5 export)."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Universe file not found: {path}")

    df = pd.read_csv(path)

    # --- Normalize ticker column ---
    ticker_cols = ["Ticker", "Symbol", "ticker"]
    ticker_col = None
    for c in ticker_cols:
        if c in df.columns:
            ticker_col = c
            break
    if ticker_col is None:
        raise ValueError(
            f"Universe file must contain a ticker column. "
            f"Looked for: {ticker_cols}. Found: {list(df.columns)}"
        )

    if ticker_col != "Ticker":
        df = df.rename(columns={ticker_col: "Ticker"})

    # --- Try to find a sector column, if any ---
    sector_candidates = [
        "Sector",
        "GICS Sector",
        "Morningstar Sector",
        "Industry",
        "sector",
    ]
    sector_col = None
    for c in sector_candidates:
        if c in df.columns:
            sector_col = c
            break

    if sector_col and sector_col != "Sector":
        df = df.rename(columns={sector_col: "Sector"})

    # --- Try to find a company/name column, if any ---
    name_candidates = [
        "Company",
        "Name",
        "Security Name",
        "Long Name",
        "company",
    ]
    name_col = None
    for c in name_candidates:
        if c in df.columns:
            name_col = c
            break

    if name_col and name_col != "Company":
        df = df.rename(columns={name_col: "Company"})

    # Make sure we at least have these columns available
    if "Sector" not in df.columns:
        df["Sector"] = None
    if "Company" not in df.columns:
        df["Company"] = None

    # For joins, a clean key
    df["Ticker_key"] = df["Ticker"].astype(str).str.strip().str.upper()

    return df


@st.cache_data
def load_weights(path: str) -> pd.DataFrame:
    """Load wave → ticker weights."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Weights file not found: {path}")

    df = pd.read_csv(path)

    required_cols = ["Wave", "Ticker", "Weight"]
    # Strip spaces from column names just in case
    df.columns = [c.strip() for c in df.columns]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Weights file must contain columns {required_cols}. "
            f"Missing: {missing}. Found: {list(df.columns)}"
        )

    # Normalize
    df["Wave"] = df["Wave"].astype(str).str.strip()
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce").fillna(0.0)

    # Drop zero‐weight rows
    df = df[df["Weight"] > 0]

    return df


# -------------------------------------------------------------------
# CORE WAVE VIEW LOGIC
# -------------------------------------------------------------------
def build_wave_view(universe: pd.DataFrame, weights: pd.DataFrame, wave_name: str):
    """
    Build holdings + sector allocation for a single wave.
    Deduplicates by ticker (summing WaveWeight).
    """
    # 1) Filter to the selected wave
    w = weights[weights["Wave"] == wave_name].copy()
    if w.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 2) Merge with universe metadata
    merged = w.merge(
        universe,
        left_on="Ticker",
        right_on="Ticker_key",
        how="left",
        suffixes=("", "_universe"),
    )

    # Name the weight column clearly
    merged = merged.rename(columns={"Weight": "WaveWeight"})

    # 3) Deduplicate by ticker – in case your CSV had duplicates
    agg_dict = {"WaveWeight": "sum"}
    if "Company" in merged.columns:
        agg_dict["Company"] = "first"
    if "Sector" in merged.columns:
        agg_dict["Sector"] = "first"

    dedup = merged.groupby("Ticker", as_index=False).agg(agg_dict)

    # 4) Build the holdings table
    cols = ["Ticker"]
    if "Company" in dedup.columns:
        cols.append("Company")
    if "Sector" in dedup.columns:
        cols.append("Sector")
    cols.append("WaveWeight")

    holdings = dedup[cols].copy().sort_values("WaveWeight", ascending=False)
    top10 = holdings.head(10).reset_index(drop=True)

    # 5) Sector allocation (if sector exists)
    sector_alloc = pd.DataFrame()
    if "Sector" in dedup.columns:
        sector_alloc = (
            dedup.groupby("Sector", dropna=False)["WaveWeight"]
            .sum()
            .reset_index()
            .rename(columns={"WaveWeight": "Weight"})
            .sort_values("Weight", ascending=False)
        )

    return holdings, top10, sector_alloc


# -------------------------------------------------------------------
# STREAMLIT UI
# -------------------------------------------------------------------
def main():
    st.title("WAVES INTELLIGENCE™ – MULTIWAVE CONSOLE")
    st.write("Equity Waves only – benchmark-aware, AI-directed, multi-mode demo.")

    # ---- Load data with clear error messages ----
    try:
        universe = load_universe(UNIVERSE_FILE)
    except Exception as e:
        st.error(f"❌ Cannot load universe file `{UNIVERSE_FILE}`.\n\nError: {e}")
        st.stop()

    try:
        weights = load_weights(WEIGHTS_FILE)
    except Exception as e:
        st.error(f"❌ Cannot load weights file `{WEIGHTS_FILE}`.\n\nError: {e}")
        st.stop()

    # ---- Wave selection ----
    waves = sorted(weights["Wave"].unique())
    if not waves:
        st.error("No waves found in weights file.")
        st.stop()

    st.sidebar.header("Wave selection")
    selected_wave = st.sidebar.selectbox("Choose Wave", waves, index=0)

    st.sidebar.caption(
        f"Universe file: `{UNIVERSE_FILE}`\n\n"
        f"Weights file: `{WEIGHTS_FILE}`"
    )

    st.subheader(f"{selected_wave} (LIVE Demo)")
    st.caption(
        "Mode: Standard – demo only; in production this flag would drive overlays, "
        "SmartSafe™, and rebalancing logic."
    )

    # ---- Build view for selected wave ----
    holdings, top10, sector_alloc = build_wave_view(universe, weights, selected_wave)

    if holdings.empty:
        st.warning(f"No holdings found for wave: {selected_wave}")
        st.stop()

    total_holdings = len(holdings)
    st.markdown(f"**Total holdings:** {total_holdings}")

    # ---- Top-10 holdings ----
    st.markdown("### Top-10 holdings (by Wave weight)")

    col_table, col_chart = st.columns([2, 1])

    with col_table:
        st.dataframe(top10, use_container_width=True)

    with col_chart:
        chart_data = top10.set_index("Ticker")["WaveWeight"]
        st.bar_chart(chart_data)

    # ---- Sector allocation ----
    st.markdown("### Sector allocation")
    if sector_alloc.empty:
        st.info("No sector information available in the universe file.")
    else:
        col_s_table, col_s_chart = st.columns([2, 1])
        with col_s_table:
            st.dataframe(sector_alloc, use_container_width=True)
        with col_s_chart:
            s_chart = sector_alloc.set_index("Sector")["Weight"]
            st.bar_chart(s_chart)


if __name__ == "__main__":
    main()