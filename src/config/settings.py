import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CLEANED_DATA_DIR = DATA_DIR / "cleaned"
MAPPING_DIR = DATA_DIR / "mappings"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
SRC_DIR = PROJECT_ROOT / "src"

RAW_DATA_FILE = RAW_DATA_DIR / "fifa_fbref_merged.csv"
CLEANED_DATA_FILE = CLEANED_DATA_DIR / "fifa_fbref_merged_cleaned.csv"
MAPPING_FILE = MAPPING_DIR / "fifa_fbref_merged_cleaning_map.csv"

DEFAULT_RAW_FILE = os.getenv("PLAYER_SCOUTING_RAW_FILE", str(RAW_DATA_FILE))
DEFAULT_CLEANED_FILE = os.getenv("PLAYER_SCOUTING_CLEANED_FILE", str(CLEANED_DATA_FILE))
DEFAULT_MAPPING_FILE = os.getenv("PLAYER_SCOUTING_MAPPING_FILE", str(MAPPING_FILE))

API_HOST = os.getenv("PLAYER_SCOUTING_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PLAYER_SCOUTING_PORT", "8010"))
