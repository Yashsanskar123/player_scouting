import importlib
from pathlib import Path

import pandas as pd

from src.config import settings
from src.data.clean_dataset import clean_dataset
from src.data.pipeline import run_pipeline
from src.features.data_quality import data_quality_report
from src.features.feature_engineering import add_player_master_features, add_team_building_features
from src.features.role_fit import compute_role_fit_scores, score_team_composition
from src.features.similarity import build_player_scouting_report, find_similar_players, optimize_squad, recommend_team_fit
from src.features.valuation import find_market_opportunities, find_transfer_market_intelligence, segment_players_by_value, score_team_chemistry
from src.models.scoring import calculate_player_scouting_score


def test_project_structure_exists():
    expected = [
        Path('src/data/clean_dataset.py'),
        Path('src/api/app.py'),
        Path('src/dashboard/app.py'),
        Path('README.md'),
        Path('requirements.txt'),
    ]

    for item in expected:
        assert item.exists(), f"Missing expected file: {item}"


def test_default_paths_point_to_workspace_data_files():
    expected_root = Path(__file__).resolve().parents[1]

    assert settings.PROJECT_ROOT == expected_root
    assert settings.DATA_DIR == expected_root / 'data'
    assert settings.RAW_DATA_FILE == expected_root / 'data' / 'raw' / 'fifa_fbref_merged.csv'
    assert settings.CLEANED_DATA_FILE == expected_root / 'data' / 'cleaned' / 'fifa_fbref_merged_cleaned.csv'
    assert settings.MAPPING_FILE == expected_root / 'data' / 'mappings' / 'fifa_fbref_merged_cleaning_map.csv'


def test_clean_dataset_creates_cleaned_csv_and_mapping(tmp_path):
    raw_file = tmp_path / 'sample.csv'
    cleaned_file = tmp_path / 'cleaned.csv'
    mapping_file = tmp_path / 'mapping.csv'

    pd.DataFrame(
        {
            'Player Name': ['Alice', 'Bob'],
            'Overall Rating': [85, 82],
            'Value (€)': [12000000, 9500000],
            'Age': [24, 27],
        }
    ).to_csv(raw_file, index=False)

    clean_dataset(str(raw_file), str(cleaned_file), str(mapping_file))

    cleaned_df = pd.read_csv(cleaned_file)
    mapping_df = pd.read_csv(mapping_file)

    assert list(cleaned_df.columns) == ['player_name', 'overall_rating', 'value', 'age']
    assert mapping_df['clean_column'].tolist() == ['player_name', 'overall_rating', 'value', 'age']
    assert cleaned_df['value'].tolist() == [12000000, 9500000]


def test_feature_engineering_adds_player_and_team_features():
    df = pd.DataFrame(
        {
            'age_fifa': [22, 31],
            'overall': [85, 70],
            'potential': [90, 75],
            'value_eur': [8000000, 2000000],
            'league_name': ['Premier League', 'Eredivisie'],
            'international_reputation': [3, 1],
        }
    )

    enriched = add_team_building_features(add_player_master_features(df))

    assert {'age_band', 'current_value_score', 'development_score', 'value_efficiency', 'is_top_league', 'is_international_level'}.issubset(enriched.columns)
    assert enriched['age_band'].tolist() == ['21-24', '29-32']
    assert enriched['is_top_league'].tolist() == [True, False]
    assert enriched['is_international_level'].tolist() == [True, False]


def test_calculate_player_scouting_score_ranks_players():
    df = pd.DataFrame(
        {
            'overall': [85, 70],
            'potential': [90, 75],
            'current_value_score': [217.5, 145.0],
            'development_score': [44.0, 24.5],
            'value_efficiency': [0.010625, 0.035],
        }
    )

    scored = calculate_player_scouting_score(df)

    assert 'scouting_score' in scored.columns
    assert scored['scouting_score'].iloc[0] > scored['scouting_score'].iloc[1]


def test_run_pipeline_creates_processed_dataset(tmp_path):
    raw_file = tmp_path / 'sample.csv'
    cleaned_file = tmp_path / 'cleaned.csv'
    mapping_file = tmp_path / 'mapping.csv'
    processed_file = tmp_path / 'processed.csv'

    pd.DataFrame(
        {
            'Player Name': ['Alice', 'Bob'],
            'Overall Rating': [85, 82],
            'Value (€)': [12000000, 9500000],
            'Age': [24, 27],
            'League Name': ['Premier League', 'Serie A'],
            'International Reputation': [3, 1],
        }
    ).to_csv(raw_file, index=False)

    run_pipeline(
        raw_path=str(raw_file),
        cleaned_path=str(cleaned_file),
        mapping_path=str(mapping_file),
        processed_path=str(processed_file),
    )

    processed_df = pd.read_csv(processed_file)

    assert processed_df['scouting_score'].notna().all()
    assert 'player_name' in processed_df.columns
    assert {'age_band', 'value_efficiency', 'is_top_league', 'is_international_level'}.issubset(processed_df.columns)
    assert {'player_name', 'overall_rating', 'value', 'age', 'league_name', 'international_reputation'}.issubset(processed_df.columns)


def test_similarity_and_team_fit_helpers_work():
    df = pd.DataFrame(
        {
            'player_name': ['Alice', 'Bob', 'Charlie'],
            'overall': [85, 82, 80],
            'potential': [90, 85, 84],
            'value_eur': [8000000, 7000000, 6500000],
            'age_fifa': [22, 24, 26],
            'pace': [79, 76, 75],
            'shooting': [77, 72, 71],
            'passing': [80, 78, 77],
            'dribbling': [78, 75, 74],
            'defending': [60, 65, 66],
            'physic': [70, 68, 67],
            'international_reputation': [3, 2, 1],
            'weak_foot': [4, 4, 3],
            'skill_moves': [4, 3, 3],
            'player_positions': ['ST, LW', 'CM', 'CB'],
            'preferred_foot': ['Right', 'Left', 'Right'],
            'league_name': ['Premier League', 'Serie A', 'Bundesliga'],
            'is_top_league': [True, False, True],
            'is_international_level': [True, False, False],
            'scouting_score': [90, 82, 78],
        }
    )

    similar = find_similar_players(df, player_identifier='Alice', top_n=2)
    team_fit = recommend_team_fit(df, target_profile={'min_overall': 80, 'max_budget_eur': 10000000, 'preferred_age': 24, 'preferred_foot': 'Right', 'target_positions': ['ST', 'LW']}, top_n=2)

    assert len(similar) >= 1
    assert 'similarity_score' in similar.columns
    assert len(team_fit) >= 1
    assert 'team_fit_score' in team_fit.columns


def test_role_fit_and_team_composition_helpers_work():
    df = pd.DataFrame(
        {
            'player_name': ['Alice', 'Bob', 'Charlie', 'Diana'],
            'overall': [85, 78, 76, 68],
            'potential': [90, 82, 80, 72],
            'age_fifa': [22, 24, 27, 31],
            'shooting': [88, 60, 62, 55],
            'passing': [72, 82, 74, 68],
            'dribbling': [78, 74, 70, 66],
            'defending': [40, 78, 76, 72],
            'pace': [81, 70, 68, 64],
            'physic': [70, 76, 75, 79],
            'player_positions': ['ST, LW', 'CM', 'CB', 'GK'],
            'preferred_foot': ['Right', 'Left', 'Right', 'Right'],
            'scouting_score': [90, 80, 78, 65],
        }
    )

    role_fit = compute_role_fit_scores(df, target_role='ST')
    team_score = score_team_composition(df, formation='4-3-3')

    assert 'role_fit_score' in role_fit.columns
    assert role_fit['role_fit_score'].iloc[0] >= role_fit['role_fit_score'].iloc[1]
    assert 'team_score' in team_score
    assert 'position_coverage' in team_score


def test_value_segmentation_and_team_chemistry_helpers_work():
    df = pd.DataFrame(
        {
            'player_name': ['Alice', 'Bob', 'Charlie', 'Diana'],
            'overall': [85, 78, 76, 68],
            'potential': [90, 82, 80, 72],
            'value_eur': [12000000, 6000000, 5000000, 1000000],
            'age_fifa': [22, 24, 27, 31],
            'player_positions': ['ST, LW', 'CM', 'CB', 'GK'],
            'preferred_foot': ['Right', 'Left', 'Right', 'Right'],
            'scouting_score': [90, 80, 78, 65],
        }
    )

    segmented = segment_players_by_value(df)
    chemistry = score_team_chemistry(df)

    assert 'value_segment' in segmented.columns
    assert 'value_performance_ratio' in segmented.columns
    assert chemistry['team_chemistry_score'] >= 0
    assert 'position_balance' in chemistry


def test_data_quality_report_returns_monitoring_metrics():
    df = pd.DataFrame(
        {
            'player_name': ['Alice', 'Bob', None],
            'overall': [85, 82, 70],
            'value_eur': [12000000, None, 1000000],
            'age_fifa': [22, 24, 31],
        }
    )

    report = data_quality_report(df)

    assert report['rows'] == 3
    assert report['columns'] == 4
    assert report['missing_values']['player_name'] == 1
    assert report['missing_values']['value_eur'] == 1
    assert report['completeness_ratio'] <= 1
    assert 'issues' in report


def test_player_scouting_report_and_market_opportunities_work():
    df = pd.DataFrame(
        {
            'player_name': ['Alice', 'Bob', 'Charlie'],
            'overall': [85, 82, 70],
            'potential': [90, 85, 75],
            'value_eur': [12000000, 6000000, 1000000],
            'age_fifa': [22, 24, 29],
            'pace': [79, 76, 70],
            'shooting': [77, 72, 68],
            'passing': [80, 78, 66],
            'dribbling': [78, 75, 68],
            'defending': [60, 65, 71],
            'physic': [70, 68, 69],
            'international_reputation': [3, 2, 1],
            'weak_foot': [4, 4, 3],
            'skill_moves': [4, 3, 2],
            'player_positions': ['ST, LW', 'CM', 'CB'],
            'preferred_foot': ['Right', 'Left', 'Right'],
            'league_name': ['Premier League', 'Serie A', 'Bundesliga'],
            'is_top_league': [True, False, True],
            'is_international_level': [True, False, False],
            'scouting_score': [90, 80, 70],
        }
    )

    report = build_player_scouting_report(df, player_identifier='Alice', target_role='ST', top_n=2)
    opportunities = find_market_opportunities(df, top_n=2)

    assert report['player']['player_name'] == 'Alice'
    assert 'similar_players' in report
    assert 'opportunity_score' in opportunities.columns
    assert opportunities.iloc[0]['player_name'] == 'Charlie'


def test_transfer_market_intelligence_and_squad_optimizer_work():
    df = pd.DataFrame(
        {
            'player_name': ['Alice', 'Bob', 'Charlie', 'Diana'],
            'overall': [85, 82, 70, 68],
            'potential': [90, 85, 75, 72],
            'value_eur': [12000000, 6000000, 1000000, 900000],
            'age_fifa': [22, 24, 29, 31],
            'player_positions': ['ST, LW', 'CM', 'CB', 'GK'],
            'league_name': ['Premier League', 'Serie A', 'Bundesliga', 'La Liga'],
            'scouting_score': [90, 80, 70, 65],
            'is_top_league': [True, False, True, True],
            'is_international_level': [True, False, False, False],
        }
    )

    transfer = find_transfer_market_intelligence(df, top_n=2)
    squad = optimize_squad(df, formation='4-3-3', top_n=4)

    assert 'fair_market_value' in transfer.columns
    assert 'transfer_value_delta' in transfer.columns
    assert squad['recommended_players']
    assert squad['team_score'] >= 0


def test_settings_support_environment_overrides(monkeypatch):
    monkeypatch.setenv('PLAYER_SCOUTING_RAW_FILE', 'custom_raw.csv')
    monkeypatch.setenv('PLAYER_SCOUTING_CLEANED_FILE', 'custom_cleaned.csv')
    monkeypatch.setenv('PLAYER_SCOUTING_MAPPING_FILE', 'custom_mapping.csv')
    monkeypatch.setenv('PLAYER_SCOUTING_HOST', '127.0.0.2')
    monkeypatch.setenv('PLAYER_SCOUTING_PORT', '9001')

    import src.config.settings as settings_module
    importlib.reload(settings_module)

    assert settings_module.DEFAULT_RAW_FILE == 'custom_raw.csv'
    assert settings_module.DEFAULT_CLEANED_FILE == 'custom_cleaned.csv'
    assert settings_module.DEFAULT_MAPPING_FILE == 'custom_mapping.csv'
    assert settings_module.API_HOST == '127.0.0.2'
    assert settings_module.API_PORT == 9001
