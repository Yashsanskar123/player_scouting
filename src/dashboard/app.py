from pathlib import Path

import pandas as pd
import streamlit as st

from src.config.settings import DEFAULT_CLEANED_FILE, API_HOST, API_PORT
from src.data.pipeline import run_pipeline
from src.features.data_quality import data_quality_report
from src.features.role_fit import compute_role_fit_scores, score_team_composition
from src.features.similarity import build_player_scouting_report, optimize_squad
from src.features.valuation import find_market_opportunities, find_transfer_market_intelligence, score_team_chemistry, segment_players_by_value


DEFAULT_PROCESSED_FILE = str(Path(DEFAULT_CLEANED_FILE).with_name('fifa_fbref_merged_processed.csv'))


def ensure_player_name_column(df: pd.DataFrame) -> pd.DataFrame:
    if 'player_name' in df.columns:
        return df

    for candidate in ('short_name', 'long_name', 'player'):
        if candidate in df.columns:
            df = df.copy()
            df['player_name'] = df[candidate]
            return df

    return df


@st.cache_data
def load_processed_data() -> pd.DataFrame:
    processed_file = Path(DEFAULT_PROCESSED_FILE)
    if not processed_file.exists():
        return pd.DataFrame()

    processed_df = pd.read_csv(processed_file)
    return ensure_player_name_column(processed_df)


st.set_page_config(page_title="Player Scouting Dashboard", layout="wide")
st.title("Player Scouting & Team Building Dashboard")
st.caption(f"API endpoint: http://{API_HOST}:{API_PORT}")

if not Path(DEFAULT_PROCESSED_FILE).exists():
    st.warning("No processed dataset detected yet. Running the pipeline now...")
    try:
        run_pipeline(
            raw_path=str(Path(DEFAULT_CLEANED_FILE).with_name('fifa_fbref_merged.csv')),
            cleaned_path=DEFAULT_CLEANED_FILE,
            mapping_path=str(Path(DEFAULT_CLEANED_FILE).with_name('fifa_fbref_merged_cleaning_map.csv')),
            processed_path=DEFAULT_PROCESSED_FILE,
        )
    except Exception as exc:
        st.error(f"Unable to build processed data: {exc}")
        st.stop()

    st.success("Pipeline completed successfully.")

processed_df = load_processed_data()

if processed_df.empty:
    st.info("No player data available yet. Add the source dataset and rerun the pipeline.")
    st.stop()

st.subheader("Player overview")

left_col, right_col = st.columns(2)
left_col.metric("Total players", len(processed_df))
right_col.metric("Top average scouting score", round(processed_df['scouting_score'].mean(), 2))

st.subheader("Player search and ranking")
search_term = st.text_input("Search player name", value="")
if search_term:
    filtered_df = processed_df[processed_df['player_name'].fillna('').str.contains(search_term, case=False, na=False)]
else:
    filtered_df = processed_df

filtered_df = filtered_df.sort_values('scouting_score', ascending=False)

st.dataframe(filtered_df[['player_name', 'overall', 'potential', 'age_fifa', 'league_name', 'scouting_score']].head(50), use_container_width=True)

st.subheader("Top scouts and role-fit candidates")
st.dataframe(filtered_df[['player_name', 'overall', 'potential', 'is_top_league', 'is_international_level', 'scouting_score']].head(20), use_container_width=True)

st.subheader("Enterprise scouting report")
role_input = st.selectbox("Target role", ['ST', 'LW', 'RW', 'CAM', 'CM', 'CDM', 'CB', 'LB', 'RB', 'GK'])
report_target = filtered_df['player_name'].iloc[0] if not filtered_df.empty else processed_df['player_name'].iloc[0]

if search_term and filtered_df.empty:
    st.warning(f"No players matched '{search_term}'. Showing the top-ranked player instead.")

try:
    report = build_player_scouting_report(processed_df, player_identifier=report_target, target_role=role_input, top_n=5)

    player = report['player']
    role_fit = report['role_fit']

    info_cols = st.columns(5)
    info_cols[0].metric("Player", player.get('player_name', 'N/A'))
    info_cols[1].metric("Overall", player.get('overall', 'N/A'))
    info_cols[2].metric("Potential", player.get('potential', 'N/A'))
    info_cols[3].metric("Age", player.get('age_fifa', 'N/A'))
    info_cols[4].metric("Scouting Score", round(player.get('scouting_score', 0), 2) if pd.notna(player.get('scouting_score')) else 'N/A')

    summary_cols = st.columns(3)
    summary_cols[0].write(f"League: {player.get('league_name', 'N/A')}")
    summary_cols[1].write(f"Preferred Foot: {player.get('preferred_foot', 'N/A')}")
    summary_cols[2].write(f"Positions: {player.get('player_positions', 'N/A')}")

    st.subheader("Similar players")
    st.dataframe(pd.DataFrame(report['similar_players']).head(10), use_container_width=True)

    st.subheader("Role fit summary")
    role_fit_df = pd.DataFrame([role_fit]).dropna(how='all')
    if not role_fit_df.empty:
        st.dataframe(role_fit_df[['player_name', 'overall', 'role_fit_score', 'player_positions']].head(10), use_container_width=True)
    else:
        st.info("No role-fit summary available for this player.")
except ValueError as exc:
    st.warning(str(exc))

st.subheader("Role-fit analysis")
role_fit_df = compute_role_fit_scores(processed_df, target_role=role_input)
st.dataframe(role_fit_df[['player_name', 'overall', 'role_fit_score', 'player_positions']].head(20), use_container_width=True)

st.subheader("Team composition")
formation_input = st.selectbox("Formation", ['4-3-3', '4-4-2', '3-5-2', '4-2-3-1'])
team_summary = score_team_composition(processed_df, formation=formation_input)
st.json(team_summary)

st.subheader("Value segmentation")
segmented_df = segment_players_by_value(processed_df)
st.dataframe(segmented_df[['player_name', 'value_eur', 'value_segment', 'value_performance_ratio']].sort_values('value_eur', ascending=False).head(20), use_container_width=True)

st.subheader("Market opportunities")
opportunities_df = find_market_opportunities(processed_df, top_n=10)
st.dataframe(opportunities_df[['player_name', 'value_eur', 'scouting_score', 'opportunity_score', 'value_opportunity']].head(20), use_container_width=True)

st.subheader("Transfer market intelligence")
transfer_df = find_transfer_market_intelligence(processed_df, top_n=10)
st.dataframe(transfer_df[['player_name', 'value_eur', 'fair_market_value', 'transfer_value_delta', 'transfer_market_score']].head(20), use_container_width=True)

st.subheader("Squad optimizer")
optimizer_summary = optimize_squad(processed_df, formation=formation_input, top_n=8)
st.json(optimizer_summary)

st.subheader("Team chemistry")
chemistry_summary = score_team_chemistry(processed_df)
st.json(chemistry_summary)

st.subheader("Data quality monitoring")
quality_summary = data_quality_report(processed_df)
st.json(quality_summary)
