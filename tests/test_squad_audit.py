import pandas as pd

from src.features.squad_audit import audit_squad, build_depth_chart


def _squad(positions: dict[str, int], **overrides) -> pd.DataFrame:
    rows = []
    i = 0
    for pos, n in positions.items():
        for j in range(n):
            rows.append({
                "player_id": f"p{i}", "short_name": f"{pos}-{j}", "canonical_position": pos,
                "performance_score": 60 + j, "age_fifa": 25,
            })
            i += 1
    df = pd.DataFrame(rows)
    for k, v in overrides.items():
        df[k] = v
    return df


def test_formation_without_wingbacks_does_not_flag_missing_wingbacks():
    # Regression test: a 4-3-3 squad with zero LWB/RWB should NOT be
    # flagged CRITICAL for missing them -- 4-3-3 doesn't use those slots
    # at all. This was the first real bug found in this module.
    squad = _squad({
        "GK": 2, "CB": 3, "LB": 2, "RB": 2, "CDM": 2, "CM": 2, "LW": 2, "RW": 2, "ST": 2,
    })
    result = audit_squad(squad, formation="4-3-3")
    messages = [f["message"] for f in result["findings"]]
    assert not any("LWB" in m or "RWB" in m for m in messages)


def test_formation_with_wingbacks_flags_missing_wingback_cover():
    squad = _squad({"GK": 2, "CB": 3, "CDM": 2, "CM": 2, "LW": 2, "RW": 2, "ST": 2})  # no LB/RB/LWB/RWB at all
    result = audit_squad(squad, formation="3-5-2")
    messages = [f["message"] for f in result["findings"]]
    assert any("LWB" in m for m in messages)
    assert any("RWB" in m for m in messages)


def test_lb_counts_toward_lwb_coverage():
    # Regression test: FIFA data frequently tags real-world wingbacks as
    # plain LB/RB with no secondary position listed at all (verified
    # against Inter's real players during development). LB should count
    # toward LWB depth coverage, not force a false "no wingback" finding.
    squad = _squad({"GK": 2, "CB": 3, "LB": 2, "RB": 2, "CDM": 2, "CM": 2, "ST": 2})
    result = audit_squad(squad, formation="3-5-2")
    messages = [f["message"] for f in result["findings"]]
    # 2 LB should satisfy LWB's minimum headcount (2), so no CRITICAL/HIGH LWB finding
    assert not any("No LWB" in m for m in messages)


def test_succession_risk_flagged_for_ageing_position_with_no_young_cover():
    squad = _squad({"GK": 1, "CB": 3, "LB": 2, "RB": 2, "CDM": 2, "CM": 2, "LW": 2, "RW": 2, "ST": 2})
    squad.loc[squad["canonical_position"] == "GK", "age_fifa"] = 34
    result = audit_squad(squad, formation="4-3-3")
    messages = [f["message"] for f in result["findings"]]
    assert any("succession" in f["category"] for f in result["findings"])


def test_succession_risk_not_flagged_when_young_cover_exists():
    squad = _squad({"GK": 2, "CB": 3, "LB": 2, "RB": 2, "CDM": 2, "CM": 2, "LW": 2, "RW": 2, "ST": 2})
    squad.loc[squad["canonical_position"] == "GK", "age_fifa"] = [34, 21]
    result = audit_squad(squad, formation="4-3-3")
    gk_succession_findings = [f for f in result["findings"] if f["category"] == "succession" and "GK" in f["message"]]
    assert len(gk_succession_findings) == 0


def test_each_finding_carries_a_usable_recruitment_filter():
    squad = _squad({"GK": 1, "CB": 1, "LB": 1, "RB": 1, "CDM": 1, "CM": 1, "LW": 1, "RW": 1, "ST": 1})
    result = audit_squad(squad, formation="4-3-3")
    depth_findings = [f for f in result["findings"] if f["category"] == "depth"]
    assert len(depth_findings) > 0
    for f in depth_findings:
        assert "canonical_position" in f["recruitment_filter"]


def test_empty_squad_returns_critical_finding_not_crash():
    result = audit_squad(pd.DataFrame(), formation="4-3-3")
    assert result["squad_health"] == 0
    assert result["findings"][0]["severity"] == "CRITICAL"


def test_unknown_formation_raises():
    squad = _squad({"GK": 2})
    try:
        audit_squad(squad, formation="not-a-real-formation")
        assert False, "should have raised"
    except ValueError:
        pass


def test_depth_chart_assigns_starter_to_highest_performance_score():
    squad = _squad({"CB": 3})
    depth_chart = build_depth_chart(squad)
    starters = depth_chart[depth_chart["depth_role"] == "starter"]
    assert len(starters) == 1
    assert starters.iloc[0]["performance_score"] == squad["performance_score"].max()

def test_audit_exposes_position_summary():
    squad = _squad({
        "GK": 2,
        "CB": 3,
        "LB": 2,
        "RB": 2,
        "CDM": 2,
        "CM": 2,
        "LW": 2,
        "RW": 2,
        "ST": 2,
    })

    result = audit_squad(
        squad,
        formation="4-3-3",
    )

    assert "position_summary" in result
    assert len(result["position_summary"]) > 0

    positions = {
        row["position"]
        for row in result["position_summary"]
    }

    assert "GK" in positions
    assert "CB" in positions
    assert "ST" in positions


def test_audit_exposes_age_profile():
    squad = _squad({
        "GK": 2,
        "CB": 3,
        "LB": 2,
        "RB": 2,
        "CDM": 2,
        "CM": 2,
        "LW": 2,
        "RW": 2,
        "ST": 2,
    })

    squad.loc[
        squad["canonical_position"] == "GK",
        "age_fifa",
    ] = [20, 34]

    result = audit_squad(
        squad,
        formation="4-3-3",
    )

    assert "age_profile" in result

    assert result["age_profile"]["u21"] == 1
    assert result["age_profile"]["31_plus"] == 1


def test_audit_exposes_performance_profile():
    squad = _squad({
        "GK": 2,
        "CB": 3,
        "LB": 2,
        "RB": 2,
        "CDM": 2,
        "CM": 2,
        "LW": 2,
        "RW": 2,
        "ST": 2,
    })

    result = audit_squad(
        squad,
        formation="4-3-3",
    )

    profile = result[
        "performance_profile"
    ]

    assert "elite_75_plus" in profile
    assert "strong_65_74" in profile
    assert "development_55_64" in profile
    assert "below_55" in profile


def test_audit_exposes_recruitment_priorities():
    squad = _squad({
        "GK": 1,
        "CB": 1,
        "LB": 1,
        "RB": 1,
        "CDM": 1,
        "CM": 1,
        "LW": 1,
        "RW": 1,
        "ST": 1,
    })

    result = audit_squad(
        squad,
        formation="4-3-3",
    )

    assert (
        "recruitment_priorities"
        in result
    )

    assert len(
        result[
            "recruitment_priorities"
        ]
    ) > 0

    first = result[
        "recruitment_priorities"
    ][0]

    assert "priority" in first
    assert "severity" in first
    assert "category" in first
    assert "need" in first
    assert "recruitment_filter" in first


def test_audit_exposes_formation_requirements():
    squad = _squad({
        "GK": 2,
        "CB": 3,
        "LB": 2,
        "RB": 2,
        "CDM": 2,
        "CM": 2,
        "LW": 2,
        "RW": 2,
        "ST": 2,
    })

    result = audit_squad(
        squad,
        formation="4-3-3",
    )

    requirements = result[
        "formation_requirements"
    ]

    assert requirements["GK"] == 1
    assert requirements["CB"] == 2
    assert requirements["ST"] == 1


def test_position_summary_marks_thin_position():
    squad = _squad({
        "GK": 2,
        "CB": 3,
        "LB": 1,
        "RB": 2,
        "CDM": 2,
        "CM": 2,
        "LW": 2,
        "RW": 2,
        "ST": 2,
    })

    result = audit_squad(
        squad,
        formation="4-3-3",
    )

    lb = next(
        row
        for row in result[
            "position_summary"
        ]
        if row["position"] == "LB"
    )

    assert lb["status"] == "thin"
    assert lb["players"] == 1