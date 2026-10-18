from pathlib import Path
import re
import shutil

import pandas as pd

from src.config.settings import (
    DEFAULT_RAW_FILE,
    DEFAULT_CLEANED_FILE,
    DEFAULT_MAPPING_FILE,
)


def normalize_column_name(col_name: str) -> str:
    text = str(col_name).strip()
    text = text.replace('%', 'pct')
    text = re.sub(r'[^0-9a-zA-Z]+', '_', text)
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text)
    text = re.sub(r'_+', '_', text).strip('_').lower()
    return text or 'column'


def resolve_raw_input(raw_path: str) -> Path:
    raw_file = Path(raw_path)
    raw_file.parent.mkdir(parents=True, exist_ok=True)

    if raw_file.exists():
        return raw_file

    downloads_candidate = Path.home() / 'Downloads' / raw_file.name
    if downloads_candidate.exists():
        shutil.copy2(downloads_candidate, raw_file)
        return raw_file

    raise FileNotFoundError(
        f"Raw file not found at {raw_file}. "
        f"Please place the dataset in data/raw or add it to Downloads."
    )


def clean_dataset(raw_path: str = DEFAULT_RAW_FILE,
                  cleaned_path: str = DEFAULT_CLEANED_FILE,
                  mapping_path: str = DEFAULT_MAPPING_FILE) -> None:
    raw_file = resolve_raw_input(raw_path)

    cleaned_file = Path(cleaned_path)
    mapping_file = Path(mapping_path)
    cleaned_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.parent.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(raw_file, low_memory=False)

    original_columns = list(raw_df.columns)
    cleaned_columns = []
    used_names = {}

    for col in original_columns:
        clean_name = normalize_column_name(col)
        if clean_name in used_names:
            used_names[clean_name] += 1
            clean_name = f"{clean_name}_{used_names[clean_name]}"
        else:
            used_names[clean_name] = 1
        cleaned_columns.append(clean_name)

    clean_df = raw_df.copy()
    clean_df.columns = cleaned_columns

    # Preserve rows and nulls; normalize obvious types only.
    for col in clean_df.columns:
        series = clean_df[col]

        if pd.api.types.is_integer_dtype(series):
            clean_df[col] = series.astype('Int64')
        elif pd.api.types.is_float_dtype(series):
            non_null = series.dropna()
            if len(non_null) == 0:
                continue
            if non_null.map(lambda x: float(x).is_integer() if pd.notna(x) else True).all():
                clean_df[col] = series.astype('Int64')

    mapping_df = pd.DataFrame({
        'original_column': original_columns,
        'clean_column': cleaned_columns,
        'notes': ['standardized column name'] * len(original_columns),
    })

    clean_df.to_csv(cleaned_file, index=False)
    mapping_df.to_csv(mapping_file, index=False)

    print(f"Cleaned dataset saved to: {cleaned_file}")
    print(f"Mapping saved to: {mapping_file}")


if __name__ == "__main__":
    clean_dataset()
