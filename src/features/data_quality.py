from __future__ import annotations

import pandas as pd


def data_quality_report(df: pd.DataFrame) -> dict[str, object]:
    """Generate a lightweight data quality summary for operational monitoring."""
    if df.empty:
        return {
            'rows': 0,
            'columns': len(df.columns),
            'missing_values': {column: 0 for column in df.columns},
            'completeness_ratio': 0,
            'issues': ['Dataset is empty.'],
        }

    missing_values = df.isna().sum().to_dict()
    total_cells = df.shape[0] * df.shape[1]
    non_missing_cells = int(total_cells - df.isna().sum().sum())

    completeness_ratio = round(non_missing_cells / total_cells, 4) if total_cells else 0

    issues = []
    for column, missing_count in missing_values.items():
        if missing_count > 0:
            issues.append(f"Column '{column}' has {missing_count} missing values.")

    duplicates = int(df.duplicated().sum())
    if duplicates:
        issues.append(f"Dataset contains {duplicates} duplicated rows.")

    return {
        'rows': int(df.shape[0]),
        'columns': int(df.shape[1]),
        'missing_values': missing_values,
        'completeness_ratio': completeness_ratio,
        'duplicate_rows': duplicates,
        'issues': issues,
    }
