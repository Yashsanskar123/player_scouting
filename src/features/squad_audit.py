"""Recruitment-grade squad audit.

The audit evaluates a real roster against the selected formation, then exposes
structural coverage, quality, age profile, succession risk and actionable
recruitment priorities. Scores remain descriptive and traceable to the roster
rather than pretending to be a universal squad-quality model.
"""
from __future__ import annotations

import pandas as pd

from src.optimization.squad_optimizer import FORMATIONS


DEPTH_MULTIPLIER = 1.5

DEPTH_TIER_LABELS = [
    "starter",
    "rotation",
    "backup",
    "prospect",
]

SUCCESSION_AGE_THRESHOLD = 30
SUCCESSION_YOUNG_THRESHOLD = 23


POSITION_COVERAGE_GROUPS = {
    "LWB": ["LWB", "LB"],
    "RWB": ["RWB", "RB"],
    "LB": ["LB", "LWB"],
    "RB": ["RB", "RWB"],
}


def _num(series):
    return pd.to_numeric(series, errors="coerce")


def _eligible_for_position(
    squad_players: pd.DataFrame,
    position: str,
) -> pd.DataFrame:

    group = POSITION_COVERAGE_GROUPS.get(
        position,
        [position],
    )

    return squad_players[
        squad_players["canonical_position"].isin(group)
    ]


def _assign_depth_tiers(
    position_group: pd.DataFrame,
) -> pd.DataFrame:

    position_group = position_group.copy()

    ranked = (
        position_group.assign(
            _perf=_num(
                position_group["performance_score"]
            )
        )
        .sort_values(
            "_perf",
            ascending=False,
            na_position="last",
        )
    )

    tiers = [
        DEPTH_TIER_LABELS[
            min(i, len(DEPTH_TIER_LABELS) - 1)
        ]
        for i in range(len(ranked))
    ]

    ranked["depth_role"] = tiers

    return ranked.drop(
        columns=["_perf"],
        errors="ignore",
    )


def build_depth_chart(
    squad_players: pd.DataFrame,
) -> pd.DataFrame:

    if squad_players.empty:
        return squad_players

    parts = []

    for _, group in squad_players.groupby(
        "canonical_position"
    ):
        parts.append(
            _assign_depth_tiers(group)
        )

    return pd.concat(parts).sort_values(
        [
            "canonical_position",
            "depth_role",
        ]
    )


def _age_profile(
    squad_players: pd.DataFrame,
) -> dict:

    ages = _num(
        squad_players["age_fifa"]
    )

    return {
        "u21": int(
            (ages < 21).sum()
        ),

        "u23": int(
            (
                (ages >= 21)
                & (ages < 23)
            ).sum()
        ),

        "23_27": int(
            (
                (ages >= 23)
                & (ages <= 27)
            ).sum()
        ),

        "28_30": int(
            (
                (ages > 27)
                & (ages <= 30)
            ).sum()
        ),

        "31_plus": int(
            (ages > 30).sum()
        ),

        "median": (
            round(
                float(ages.median()),
                1,
            )
            if pd.notna(ages.median())
            else None
        ),

        "mean": (
            round(
                float(ages.mean()),
                1,
            )
            if pd.notna(ages.mean())
            else None
        ),
    }


def _performance_profile(
    squad_players: pd.DataFrame,
) -> dict:

    scores = _num(
        squad_players["performance_score"]
    )

    return {
        "average": (
            round(
                float(scores.mean()),
                1,
            )
            if pd.notna(scores.mean())
            else None
        ),

        "median": (
            round(
                float(scores.median()),
                1,
            )
            if pd.notna(scores.median())
            else None
        ),

        "elite_75_plus": int(
            (scores >= 75).sum()
        ),

        "strong_65_74": int(
            (
                (scores >= 65)
                & (scores < 75)
            ).sum()
        ),

        "development_55_64": int(
            (
                (scores >= 55)
                & (scores < 65)
            ).sum()
        ),

        "below_55": int(
            (scores < 55).sum()
        ),
    }


def _position_summary(
    squad_players: pd.DataFrame,
    starters_required: dict,
) -> list[dict]:

    rows = []

    positions = list(
        dict.fromkeys(
            list(starters_required)
            + list(
                squad_players[
                    "canonical_position"
                ]
                .dropna()
                .unique()
            )
        )
    )

    for position in positions:

        group = _eligible_for_position(
            squad_players,
            position,
        )

        scores = _num(
            group["performance_score"]
        )

        ages = _num(
            group["age_fifa"]
        )

        required = int(
            starters_required.get(
                position,
                0,
            )
        )

        if position == "GK":
            target = 2
        elif required:
            target = max(
                2,
                int(
                    required
                    * DEPTH_MULTIPLIER
                    + 0.9999
                ),
            )
        else:
            target = 0

        count = len(group)

        best = scores.max()
        avg = scores.mean()

        if required == 0:
            status = "squad-only"

        elif count == 0:
            status = "missing"

        elif count < target:
            status = "thin"

        elif (
            pd.notna(best)
            and best < 55
        ):
            status = "quality concern"

        else:
            status = "covered"

        rows.append(
            {
                "position": position,

                "required_starters": required,

                "target_depth": target,

                "players": count,

                "coverage_pct": (
                    round(
                        min(
                            100,
                            count
                            / target
                            * 100,
                        ),
                        1,
                    )
                    if target
                    else 100.0
                ),

                "best_performance": (
                    round(
                        float(best),
                        1,
                    )
                    if pd.notna(best)
                    else None
                ),

                "average_performance": (
                    round(
                        float(avg),
                        1,
                    )
                    if pd.notna(avg)
                    else None
                ),

                "median_age": (
                    round(
                        float(
                            ages.median()
                        ),
                        1,
                    )
                    if pd.notna(
                        ages.median()
                    )
                    else None
                ),

                "status": status,
            }
        )

    return rows


def audit_squad(
    squad_players: pd.DataFrame,
    formation: str = "4-3-3",
) -> dict:

    if formation not in FORMATIONS:
        raise ValueError(
            f"Unknown formation '{formation}'. "
            f"Available: {list(FORMATIONS)}"
        )

    starters_required = FORMATIONS[
        formation
    ]

    min_headcount_by_position = {
        pos: (
            2
            if pos == "GK"
            else max(
                2,
                int(
                    count
                    * DEPTH_MULTIPLIER
                    + 0.9999
                ),
            )
        )
        for pos, count
        in starters_required.items()
    }

    # ---------------------------------------------------------
    # EMPTY SQUAD
    # ---------------------------------------------------------

    if squad_players.empty:

        return {
            "squad_health": 0,
            "depth_score": 0,
            "age_score": 0,

            "average_performance_score": None,
            "median_age": None,
            "squad_size": 0,

            "findings": [
                {
                    "severity": "CRITICAL",
                    "category": "roster",
                    "message": (
                        "Squad has no players assigned yet."
                    ),
                    "recruitment_filter": {},
                }
            ],

            "depth_chart": pd.DataFrame(),

            "position_summary": [],

            "age_profile": {
                "u21": 0,
                "u23": 0,
                "23_27": 0,
                "28_30": 0,
                "31_plus": 0,
                "median": None,
                "mean": None,
            },

            "performance_profile": {
                "average": None,
                "median": None,
                "elite_75_plus": 0,
                "strong_65_74": 0,
                "development_55_64": 0,
                "below_55": 0,
            },

            "recruitment_priorities": [],
        }

    # ---------------------------------------------------------
    # DEPTH
    # ---------------------------------------------------------

    depth_chart = build_depth_chart(
        squad_players
    )

    findings = []

    # ---------------------------------------------------------
    # POSITION HEADCOUNT
    # ---------------------------------------------------------

    for (
        position,
        min_count,
    ) in min_headcount_by_position.items():

        have = len(
            _eligible_for_position(
                squad_players,
                position,
            )
        )

        if have == 0:

            findings.append(
                {
                    "severity": "CRITICAL",
                    "category": "depth",

                    "message": (
                        f"No {position} "
                        "(or LB/RB-adjacent cover) "
                        f"on the roster at all -- "
                        f"required by the {formation} system."
                    ),

                    "recruitment_filter": {
                        "canonical_position": position
                    },
                }
            )

        elif have < min_count:

            findings.append(
                {
                    "severity": "HIGH",
                    "category": "depth",

                    "message": (
                        f"Only {have} player(s) able "
                        f"to cover {position} on the "
                        f"roster; {min_count} is the "
                        f"minimum for safe rotation "
                        f"in a {formation}."
                    ),

                    "recruitment_filter": {
                        "canonical_position": position
                    },
                }
            )

    # ---------------------------------------------------------
    # QUALITY
    # ---------------------------------------------------------

    for (
        position,
        group,
    ) in squad_players.groupby(
        "canonical_position"
    ):

        scores = _num(
            group["performance_score"]
        )

        best_score = scores.max()

        if (
            pd.notna(best_score)
            and best_score < 55
        ):

            findings.append(
                {
                    "severity": "MEDIUM",
                    "category": "quality",

                    "message": (
                        f"Best available {position} "
                        f"has a performance score "
                        f"of only {best_score:.1f} "
                        "-- weak starting option."
                    ),

                    "recruitment_filter": {
                        "canonical_position": position,
                        "min_performance_score": 65,
                    },
                }
            )

    # ---------------------------------------------------------
    # SUCCESSION
    # ---------------------------------------------------------

    for (
        position,
        group,
    ) in squad_players.groupby(
        "canonical_position"
    ):

        ages = _num(
            group["age_fifa"]
        )

        scores = _num(
            group["performance_score"]
        )

        if (
            group.empty
            or not scores.notna().any()
        ):
            continue

        best_idx = scores.idxmax()

        best_age = ages.loc[
            best_idx
        ]

        has_young_cover = (
            (
                ages
                < SUCCESSION_YOUNG_THRESHOLD
            )
            & (
                group.index
                != best_idx
            )
        ).any()

        if (
            pd.notna(best_age)
            and best_age
            >= SUCCESSION_AGE_THRESHOLD
            and not has_young_cover
        ):

            findings.append(
                {
                    "severity": "HIGH",
                    "category": "succession",

                    "message": (
                        f"Best {position} "
                        f"is {int(best_age)} "
                        f"with no player under "
                        f"{SUCCESSION_YOUNG_THRESHOLD} "
                        "behind them."
                    ),

                    "recruitment_filter": {
                        "canonical_position": position,
                        "max_age": 24,
                    },
                }
            )

    # ---------------------------------------------------------
    # HEADLINE SCORES
    # ---------------------------------------------------------

    avg_performance = _num(
        squad_players[
            "performance_score"
        ]
    ).mean()

    positions_covered = sum(
        len(
            _eligible_for_position(
                squad_players,
                position,
            )
        )
        >= required
        for (
            position,
            required,
        ) in min_headcount_by_position.items()
    )

    depth_score = (
        round(
            positions_covered
            / len(
                min_headcount_by_position
            )
            * 100,
            1,
        )
        if min_headcount_by_position
        else 100.0
    )

    ages = _num(
        squad_players["age_fifa"]
    )

    median_age = ages.median()

    age_score = (
        round(
            max(
                0,
                100
                - abs(
                    median_age
                    - 25.5
                )
                * 12,
            ),
            1,
        )
        if pd.notna(median_age)
        else 50.0
    )

    critical_count = sum(
        f["severity"] == "CRITICAL"
        for f in findings
    )

    high_count = sum(
        f["severity"] == "HIGH"
        for f in findings
    )

    medium_count = sum(
        f["severity"] == "MEDIUM"
        for f in findings
    )

    squad_health = round(
        max(
            0,
            (
                avg_performance
                if pd.notna(
                    avg_performance
                )
                else 50
            )
            - critical_count * 15
            - high_count * 7
            - medium_count * 3,
        ),
        1,
    )

    # ---------------------------------------------------------
    # FINDING ORDER
    # ---------------------------------------------------------

    severity_order = {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
    }

    findings.sort(
        key=lambda f:
        severity_order[
            f["severity"]
        ]
    )

    # ---------------------------------------------------------
    # RECRUITMENT PRIORITIES
    # ---------------------------------------------------------

    priorities = []

    for idx, finding in enumerate(
        findings,
        start=1,
    ):

        priorities.append(
            {
                "priority": idx,

                "severity":
                    finding["severity"],

                "category":
                    finding["category"],

                "need":
                    finding["message"],

                "recruitment_filter":
                    finding[
                        "recruitment_filter"
                    ],
            }
        )

    # ---------------------------------------------------------
    # FINAL RESULT
    # ---------------------------------------------------------

    return {
        "squad_health": squad_health,

        "depth_score": depth_score,

        "age_score": age_score,

        "average_performance_score": (
            round(
                float(
                    avg_performance
                ),
                1,
            )
            if pd.notna(
                avg_performance
            )
            else None
        ),

        "median_age": (
            round(
                float(median_age),
                1,
            )
            if pd.notna(
                median_age
            )
            else None
        ),

        "squad_size":
            len(squad_players),

        "formation_requirements": {
            k: int(v)
            for k, v
            in starters_required.items()
        },

        "position_summary":
            _position_summary(
                squad_players,
                starters_required,
            ),

        "age_profile":
            _age_profile(
                squad_players
            ),

        "performance_profile":
            _performance_profile(
                squad_players
            ),

        "findings":
            findings,

        "recruitment_priorities":
            priorities,

        "depth_chart":
            depth_chart,

        "methodology": {
            "depth": (
                "Formation-specific starter "
                "requirements with a 1.5x depth "
                "target for outfield positions "
                "and two goalkeepers."
            ),

            "succession": (
                "Flags an age-30+ best player "
                "when there is no teammate under "
                "23 at the same canonical position."
            ),

            "quality": (
                "Flags a position when its best "
                "available performance score is "
                "below 55."
            ),

            "age_balance": (
                "Descriptive balance signal around "
                "a median age of 25.5; it is not a "
                "claim that one age is universally optimal."
            ),
        },
    }