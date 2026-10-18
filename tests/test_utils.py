import numpy as np
import pandas as pd

from src.utils import to_native


def test_numpy_int64_converted_to_native_int():
    result = to_native(np.int64(42))
    assert result == 42
    assert isinstance(result, int)
    assert not isinstance(result, np.integer)


def test_numpy_float64_converted_to_native_float():
    result = to_native(np.float64(3.14))
    assert isinstance(result, float)
    assert not isinstance(result, np.floating)


def test_numpy_nan_converted_to_none():
    assert to_native(np.float64("nan")) is None


def test_pandas_na_converted_to_none():
    assert to_native(pd.NA) is None


def test_regular_python_values_pass_through():
    assert to_native("LOW") == "LOW"
    assert to_native(5) == 5
    assert to_native(5.5) == 5.5
    assert to_native(None) is None


def test_series_value_from_real_dataframe_row_is_json_safe():
    # This is the exact failure mode found three times in this project
    # (routers_v2.py's /value, /risk endpoints; replacement_finder.py;
    # comparison.py) -- a value pulled from a pandas row via .get() or
    # column indexing comes back as a numpy scalar that pydantic/json
    # can't serialize. Simulate that exact access pattern here.
    df = pd.DataFrame([{"age_fifa": 25, "value_eur": 1_000_000.0}])
    row = df.iloc[0]
    age_native = to_native(row.get("age_fifa"))
    value_native = to_native(row.get("value_eur"))
    import json
    json.dumps({"age": age_native, "value": value_native})  # must not raise
