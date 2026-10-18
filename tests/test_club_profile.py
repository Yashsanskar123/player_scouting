import pytest

from src.features import club_profile as cp


@pytest.fixture(autouse=True)
def tmp_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "PROFILE_PATH", tmp_path / "club_profile.json")


def test_save_load_clear_roundtrip():
    assert cp.load_profile() is None
    saved = cp.save_profile("Arsenal", "4-3-3", 150_000_000, None, valid_clubs={"Arsenal"})
    assert cp.load_profile()["club_name"] == "Arsenal"
    assert saved["transfer_budget_eur"] == 150_000_000 and saved["wage_budget_eur"] is None
    cp.clear_profile()
    cp.clear_profile()  # clearing twice is fine
    assert cp.load_profile() is None


@pytest.mark.parametrize("kwargs", [
    dict(club_name="", formation="4-3-3"),
    dict(club_name="Nowhere FC", formation="4-3-3"),
    dict(club_name="Arsenal", formation="9-9-9"),
    dict(club_name="Arsenal", formation="4-3-3", transfer_budget_eur=-5),
    dict(club_name="Arsenal", formation="4-3-3", transfer_budget_eur="abc"),
])
def test_validation_rejects_bad_input(kwargs):
    with pytest.raises(ValueError):
        cp.save_profile(valid_clubs={"Arsenal"}, **kwargs)
    assert cp.load_profile() is None  # nothing written on failure
