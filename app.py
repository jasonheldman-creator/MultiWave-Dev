import pathlib
import pandas as pd
import streamlit as st

# ---------- CONFIG ----------

UNIVERSE_FILE = "Master_Stock_Sheet - Sheet5.csv"
WEIGHTS_FILE = "wave_weights.csv"

st.set_page_config(
    page_title="WAVES INTELLIGENCE – MultiWave Console",
    layout="wide",
)

# ---------- HELPERS ----------

def load_universe(path: str) -> pd.DataFrame:
    """Load the master stock universe and normalize column names."""
    df = pd.read_csv(path)

    # Keep a copy of original columns for display
    df.columns = [c.strip() for c in df.columns]

    # Build a normalized name map for convenience
    lower_map = {c.lower().strip(): c for c in df.columns}

    # Best-guess for key fields
    ticker_col = lower_map.get("ticker")
    name_col = lower_map.get("name") or lower_map.get("company")
    sector_col = lower_map.get("sector")

    # Standardize field names if they exist
    rename_map = {}
    if ticker_col and ticker_col != "Ticker":
        rename_map[ticker_col] = "Ticker"
    if name_col and name_col != "Company":
        rename_map[name_col] = "Company"
    if sector_col and sector_col != "Sector":
        rename_map[sector_col] = "Sector"
    if rename_map:
        df = df.rename(columns=rename_map)

    # Clean ticker for joins
    if "Ticker" in df.columns:
        df["Ticker_key"] = df["Ticker"].astype(str).str.upper().str.strip()
    else:
        raise ValueError(
            f"Universe file '{path}' must contain a 'Ticker' column. "
            f"Found columns: {list(df.columns)}"
        )

    return df


def load_wave_weights(path: str) -> pd.DataFrame:
    """Load wave weights CSV and ensure columns Wave, Ticker, Weight exist."""
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    required = ["Wave", "Ticker", "Weight"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Weights file must contain columns {required}. "
            f"Missing: {missing}. Found: {list(df.columns)}"
        )

    # Clean up
    df = df.dropna(subset=["Wave", "Ticker", "Weight"])
    df["Wave"] = df["Wave"].astype(str).str.strip()
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce")
    df = df.dropna(subset=["Weight"])

    # Optional: normalize so each Wave sums to 1.0 (for presentation)
    def normalize(group):
        total = group["Weight"].sum()
        if total and total > 0:
            group["Weight"] = group["Weight"] / total
        return group

    df = df.groupby("Wave", group_keys=False).apply(normalize)

    return df


@st.cache_data(show_spinner=False)
def load_all_data():
    universe = load_universe(UNIVERSE_FILE)
    weights = load_wave_weights(WEIGHTS_FILE)
    return universe, weights


def build_wave_view(universe: pd.DataFrame, weights: pd.DataFrame, wave_name: str):
    """Return merged holdings for a single wave."""
    w = weights[weights["Wave"] == wave_name].copy()

    if w.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Join on cleaned ticker
    merged = w.merge(
        universe,
        left_on="Ticker",
        right_on="Ticker_key",
        how="left",
        suffixes=("", "_universe"),
    )

    # Friendly columns for the main table
    cols = []

    if "Ticker" in merged.columns:
        cols.append("Ticker")
    if "Company" in merged.columns:
        cols.append("Company")
    if "Sector" in merged.columns:
        cols.append("Sector")

    merged = merged.rename(columns={"Weight": "WaveWeight"})

    if "WaveWeight" in merged.columns:
        cols.append("WaveWeight")

    # If we somehow have none of those, just show everything
    if not cols:
        cols = merged.columns.tolist()

    holdings = merged[cols].copy()

    # Top-10 by Wave weight
    if "WaveWeight" in holdings.columns:
        holdings = holdings.sort_values("WaveWeight", ascending=False)

    top10 = holdings.head(10).reset_index(drop=True)

    # Sector allocation
    sector_alloc = pd.DataFrame()
    if "Sector" in merged.columns and "WaveWeight" in merged.columns:
        sector_alloc = (
            merged.groupby("Sector", dropna=False)["WaveWeight"]
            .sum()
            .reset_index()
            .rename(columns={"WaveWeight": "Weight"})
            .sort_values("Weight", ascending=False)
        )

    return top10, sector_alloc


# ---------- MAIN APP ----------

def main():
    st.title("WAVES INTELLIGENCE™ – MULTIWAVE CONSOLE")
    st.caption("Equity Waves only – benchmark-aware, AI-directed, multi-mode demo.")

    # Try to load data up front
    try:
        universe, weights = load_all_data()
    except FileNotFoundError as e:
        st.error(
            f"Cannot find data file.\n\n"
            f"Make sure **{UNIVERSE_FILE}** and **{WEIGHTS_FILE}** "
            f"are uploaded to the repo root.\n\nError: {e}"
        )
        st.stop()
    except ValueError as e:
        st.error(f"Data problem:\n\n{e}")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error while loading data:\n\n{e}")
        st.stop()

    # Sidebar – wave selection
    st.sidebar.header("Wave selector")

    available_waves = sorted(weights["Wave"].unique().tolist())
    if not available_waves:
        st.sidebar.error("No waves found in wave_weights.csv")
        st.stop()

    selected_wave = st.sidebar.selectbox("Choose a Wave", available_waves, index=0)

    # Optional: show quick stats in sidebar
    num_holdings = (weights["Wave"] == selected_wave).sum()
    st.sidebar.markdown(f"**Holdings in this Wave:** {num_holdings}")

    st.markdown(f"### {selected_wave} (LIVE Demo)")
    st.caption(
        "Mode: Standard – demo only; in production this flag would drive overlays, "
        "SmartSafe™, and rebalancing logic."
    )

    # Build per-wave view
    top10, sector_alloc = build_wave_view(universe, weights, selected_wave)

    if top10.empty:
        st.warning(f"No holdings found for **{selected_wave}** in wave_weights.csv.")
        st.stop()

    col_table, col_chart = st.columns([1.2, 1])

    with col_table:
        st.subheader("Top-10 holdings (by Wave weight)")
        st.dataframe(
            top10,
            use_container_width=True,
            hide_index=True,
        )

    with col_chart:
        if "Ticker" in top10.columns and "WaveWeight" in top10.columns:
            st.subheader("Top-10 by Wave weight – chart")
            # Basic bar chart
            chart_data = top10.set_index("Ticker")["WaveWeight"]
            st.bar_chart(chart_data)
        else:
            st.info("Wave weight chart unavailable – missing Ticker / WaveWeight columns.")

    st.markdown("---")

    st.subheader("Sector allocation")
    if not sector_alloc.empty:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            st.dataframe(
                sector_alloc,
                use_container_width=True,
                hide_index=True,
            )
        with c2:
            st.bar_chart(
                sector_alloc.set_index("Sector")["Weight"]
            )
    else:
        st.info(
            "Sector column not found in the universe file – "
            "sector allocation view is disabled."
        )

    # Footer
    st.markdown("---")
    st.caption(
        "WAVES Intelligence™ demo – MultiWave view. "
        "Data and weights for illustration only; not investment advice."
    )


if __name__ == "__main__":
    main()