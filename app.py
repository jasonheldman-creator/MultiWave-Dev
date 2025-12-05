import streamlit as st
import pandas as pd

# ---------- FILENAMES (repo root) ----------
UNIVERSE_FILE = "Master_Stock_Sheet - Sheet5.csv"
WEIGHTS_FILE = "wave_weights.csv"

st.set_page_config(
    page_title="WAVES INTELLIGENCE – MultiWave Console",
    layout="wide",
)

# ---------- LOADERS WITH CACHING ----------
@st.cache_data
def load_universe(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    if "Ticker" not in df.columns:
        raise ValueError(f"Universe file {path} must contain a 'Ticker' column.")

    # Standardize tickers
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()

    return df


@st.cache_data
def load_wave_weights(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    expected_cols = {"Wave", "Ticker", "Weight"}
    missing = expected_cols.difference(df.columns)
    if missing:
        raise ValueError(
            f"Weights file {path} must contain columns {sorted(expected_cols)}. "
            f"Missing: {sorted(missing)}. Found: {list(df.columns)}"
        )

    df["Wave"] = df["Wave"].astype(str).str.strip()
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce").fillna(0.0)

    return df


def safe_load_data():
    """Load universe + weights, show a clear error and stop if anything is wrong."""
    try:
        universe = load_universe(UNIVERSE_FILE)
    except Exception as e:
        st.error(f"❌ Cannot load universe file `{UNIVERSE_FILE}`.\n\nError: {e}")
        st.stop()

    try:
        weights = load_wave_weights(WEIGHTS_FILE)
    except Exception as e:
        st.error(f"❌ Cannot load weights file `{WEIGHTS_FILE}`.\n\nError: {e}")
        st.stop()

    return universe, weights


# ---------- MAIN APP ----------
def main():
    st.markdown(
        "<h1 style='font-weight:700;'>WAVES INTELLIGENCE™ – MULTIWAVE CONSOLE</h1>",
        unsafe_allow_html=True,
    )
    st.write("Equity Waves only – benchmark-aware, AI-directed, multi-mode demo.")

    universe, weights = safe_load_data()

    # Available Waves from the weights file
    available_waves = sorted(weights["Wave"].unique())

    # ----- SIDEBAR -----
    with st.sidebar:
        st.header("Wave selection")

        wave_name = st.selectbox(
            "Select Wave",
            options=available_waves,
            index=0 if available_waves else None,
        )

        mode = st.radio(
            "Mode",
            options=["Standard", "Alpha-Minus-Beta", "Private Logic™"],
            index=0,
            help="For this demo, all modes use the same holdings. "
                 "In production, risk overlays would differ by mode.",
        )

    if not available_waves:
        st.warning("No Waves found in the weights file.")
        st.stop()

    # Filter weights to the selected Wave
    wave_weights = weights[weights["Wave"] == wave_name].copy()

    if wave_weights.empty:
        st.warning(f"No holdings found for Wave: **{wave_name}**.")
        st.stop()

    # Merge with universe to pull in company / sector / etc.
    merged = pd.merge(
        wave_weights,
        universe,
        on="Ticker",
        how="left",
        suffixes=("", "_universe"),
    )

    # Rename the Wave's own weight so it is clearly separate from any universe weight
    if "Weight" in merged.columns:
        merged.rename(columns={"Weight": "WaveWeight"}, inplace=True)

    # If the universe also has a "Weight" column, it will be called "Weight_universe"
    # by the merge above – so there are no duplicate column names.

    # ---------- TOP PANEL ----------
    st.subheader(f"{wave_name} (LIVE Demo)")
    st.caption(
        f"Mode: **{mode}** – demo only; in production this flag would drive overlays, "
        f"SmartSafe™, and rebalancing logic."
    )

    total_holdings = len(wave_weights)
    st.write(f"**Total holdings:** {total_holdings}")

    # ---------- TOP-10 HOLDINGS BY WAVE WEIGHT ----------
    if "WaveWeight" not in merged.columns:
        st.error(
            "WaveWeight column not found after merge. "
            "Check that the weights file includes a numeric 'Weight' column."
        )
        st.stop()

    merged["WaveWeight"] = pd.to_numeric(merged["WaveWeight"], errors="coerce").fillna(0.0)

    top10 = merged.sort_values("WaveWeight", ascending=False).head(10)

    left_col, right_col = st.columns([2, 2])

    with left_col:
        st.markdown("### Top-10 holdings (by Wave weight)")

        display_cols = []
        for c in ["Ticker", "Company", "Sector", "WaveWeight"]:
            if c in top10.columns:
                display_cols.append(c)

        st.dataframe(
            top10[display_cols].reset_index(drop=True),
            use_container_width=True,
        )

    with right_col:
        st.markdown("### Top-10 by Wave weight – chart")

        chart_data = top10.set_index("Ticker")["WaveWeight"]
        st.bar_chart(chart_data)

    # ---------- SECTOR ALLOCATION ----------
    if "Sector" in merged.columns:
        st.markdown("### Sector allocation")

        sector_alloc = (
            merged.groupby("Sector")["WaveWeight"]
            .sum()
            .sort_values(ascending=False)
        )

        st.dataframe(
            sector_alloc.reset_index().rename(columns={"WaveWeight": "WaveWeightSum"}),
            use_container_width=True,
        )
    else:
        st.info(
            "No **Sector** column found in the universe file. "
            "Add a Sector column to see sector allocation."
        )

    st.markdown("---")
    st.caption(
        "Universe: derived from `Master_Stock_Sheet - Sheet5.csv`. "
        "Wave definitions & weights from `wave_weights.csv`."
    )


if __name__ == "__main__":
    main()