from src.features.season_context import build_season_catalog, season_label


def test_season_label():
    assert season_label(1718) == "2017/18"
    assert season_label(2425) == "2024/25"


def test_catalog_marks_latest_current():
    seasons = build_season_catalog([2425, 1819, 2223])
    assert [s.season for s in seasons] == [1819, 2223, 2425]
    assert seasons[-1].status == "current"
    assert seasons[-1].label == "2024/25"
