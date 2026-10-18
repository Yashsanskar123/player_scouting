from pathlib import Path

import pandas as pd

from src.data.clean_dataset import clean_dataset
from src.features.feature_engineering import add_player_master_features, add_team_building_features
from src.models.scoring import calculate_player_scouting_score


def run_pipeline(
    raw_path: str,
    cleaned_path: str,
    mapping_path: str,
    processed_path: str,
) -> pd.DataFrame:
    """Run the player-scouting ETL and analytics pipeline for a source dataset."""
    clean_dataset(raw_path=raw_path, cleaned_path=cleaned_path, mapping_path=mapping_path)

    processed_file = Path(processed_path)
    processed_file.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(cleaned_path, low_memory=False)

    df = add_player_master_features(df)
    df = add_team_building_features(df)
    df = calculate_player_scouting_score(df)

    df.to_csv(processed_file, index=False)

    return df
