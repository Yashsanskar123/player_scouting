"""Shared helpers. Currently just the numpy/pandas -> native-Python
scalar converter needed anywhere a pandas Series value is put directly
into an API response -- pydantic's JSON encoder doesn't know how to
serialize numpy.int64/float64/Categorical on its own, and this bug has
bitten more than one endpoint in this codebase already (see git history
on src/api/routers_v2.py). Centralized here instead of copy-pasted so the
next new endpoint doesn't reintroduce it.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def to_native(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if math.isnan(value) else float(value)
    if isinstance(value, pd.Categorical) or type(value).__name__ == "CategoricalDtype":
        return str(value) if pd.notna(value) else None
    if isinstance(value, list):
        return [to_native(item) for item in value]
    if isinstance(value, tuple):
        return tuple(to_native(item) for item in value)
    if isinstance(value, dict):
        return {str(key): to_native(item) for key, item in value.items()}
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    # pandas Categorical scalar values (e.g. from a `pd.cut` column) come
    # through as numpy str_ or plain str already in most pandas versions,
    # but guard explicitly since "LOW"/"MEDIUM"/"HIGH" tier values have
    # caused this exact serialization error once already.
    if isinstance(value, np.str_):
        return str(value)
    return value
