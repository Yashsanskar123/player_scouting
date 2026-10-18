import pandas as pd

from src.features.tactical_fit import FORMATION_ROLES, STYLE_PROFILES, score_tactical_fit


def test_tactical_fit_is_bounded_and_explainable():
    row = pd.Series({
        "player_id": "p1", "short_name": "Test Player", "canonical_position": "CM",
        "per_90_minutes_prg_c_pctile": 80, "per_90_minutes_prg_p_pctile": 75,
        "per_90_minutes_prg_r_pctile": 70, "per_90_minutes_ppa_pctile": 65,
        "per_90_minutes_total_cmp_pctile": 85, "total_cmppct_pctile": 82,
        "per_90_minutes_1_3_pctile": 78, "per_90_minutes_ast_pctile": 70,
        "per_90_minutes_expected_x_a_pctile": 72, "per_90_minutes_kp_pctile": 68,
        "sca_sca90_pctile": 74, "per_90_minutes_gls_pctile": 55,
        "per_90_minutes_x_g_pctile": 58, "per_90_minutes_npx_g_pctile": 57,
        "per_90_minutes_tackles_tkl_pctile": 66, "per_90_minutes_int_pctile": 61,
        "per_90_minutes_tkl_int_pctile": 63, "per_90_minutes_blocks_blocks_pctile": 59,
        "per_90_minutes_clr_pctile": 52, "pace": 78, "physic": 80, "defending": 76,
    })
    result = score_tactical_fit(row, "4-3-3", "Possession")
    assert 0 <= result["system_fit_score"] <= 100
    assert 0 < result["evidence_coverage_pct"] <= 100
    assert result["formation"] == "4-3-3"
    assert result["style"] == "Possession"
    assert result["strengths"]
    assert "note" in result


def test_supported_contexts_are_explicit():
    assert {"4-3-3", "4-2-3-1", "4-4-2", "3-4-3", "3-5-2"} <= set(FORMATION_ROLES)
    assert {"Balanced", "Possession", "High Press", "Transition", "Low Block"} <= set(STYLE_PROFILES)
