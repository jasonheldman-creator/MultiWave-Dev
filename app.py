def build_wave_view(universe: pd.DataFrame, weights: pd.DataFrame, wave_name: str):
    """Return merged holdings for a single wave, with one row per ticker."""

    # 1) Filter to a single wave
    w = weights[weights["Wave"] == wave_name].copy()
    if w.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 2) Merge weights ↔ universe on ticker
    merged = w.merge(
        universe,
        left_on="Ticker",
        right_on="Ticker_key",
        how="left",
        suffixes=("", "_universe"),
    ).rename(columns={"Weight": "WaveWeight"})

    # 3) Collapse any duplicate tickers:
    #    - sum WaveWeight
    #    - take first Company / Sector
    agg_dict = {"WaveWeight": "sum"}
    if "Company" in merged.columns:
        agg_dict["Company"] = "first"
    if "Sector" in merged.columns:
        agg_dict["Sector"] = "first"

    dedup = (
        merged.groupby("Ticker", as_index=False)
        .agg(agg_dict)
    )

    # 4) Build holdings table (unique tickers, sorted by weight)
    cols = ["Ticker"]
    if "Company" in dedup.columns:
        cols.append("Company")
    if "Sector" in dedup.columns:
        cols.append("Sector")
    cols.append("WaveWeight")

    holdings = dedup[cols].copy().sort_values("WaveWeight", ascending=False)
    top10 = holdings.head(10).reset_index(drop=True)

    # 5) Sector allocation from the deduplicated rows
    sector_alloc = pd.DataFrame()
    if "Sector" in dedup.columns:
        sector_alloc = (
            dedup.groupby("Sector", dropna=False)["WaveWeight"]
            .sum()
            .reset_index()
            .rename(columns={"WaveWeight": "Weight"})
            .sort_values("Weight", ascending=False)
        )

    return top10, sector_alloc