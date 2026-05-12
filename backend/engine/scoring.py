
from typing import Any

# Issue-type base weights (how much each type costs per affected row-%)
ISSUE_TYPE_WEIGHTS = {
    "missing_values":       {"critical": 18, "warning": 8,  "info": 2},
    "duplicate_rows":       {"critical": 15, "warning": 10, "info": 3},
    "datatype_mismatch":    {"critical": 12, "warning": 6,  "info": 1},
    "range_violation":      {"critical": 20, "warning": 10, "info": 2},
    "negative_value":       {"critical": 20, "warning": 10, "info": 2},
    "regex_violation":      {"critical": 10, "warning": 5,  "info": 1},
    "invalid_category":     {"critical": 12, "warning": 6,  "info": 1},
    "date_order_violation": {"critical": 20, "warning": 12, "info": 2},
    "anomaly":              {"critical": 8,  "warning": 4,  "info": 1},
}

DEFAULT_ISSUE_WEIGHT = {"critical": 10, "warning": 5, "info": 1}

# Column patterns → importance multiplier
COLUMN_IMPORTANCE_PATTERNS = {
    "id":         2.0,
    "email":      1.8,
    "date":       1.6,
    "salary":     1.5,
    "price":      1.5,
    "amount":     1.5,
    "revenue":    1.5,
    "age":        1.3,
    "name":       1.2,
    "score":      1.2,
    "status":     1.2,
}

SEVERITY_MULTIPLIERS = {"critical": 3.0, "warning": 1.5, "info": 0.5}


def _column_importance(col_name: str, user_importance: dict = None) -> float:
    """Return column importance multiplier."""
    if user_importance and col_name in user_importance:
        return float(user_importance[col_name])
    col_lower = col_name.lower()
    for pattern, mult in COLUMN_IMPORTANCE_PATTERNS.items():
        if pattern in col_lower:
            return mult
    return 1.0


def compute_score(
    issues: list[dict],
    anomalies: dict,
    total_rows: int,
    total_cols: int,
    user_importance: dict = None,
) -> dict:
    """
    Returns:
    {
      score: 0-100,
      grade: A/B/C/D/F,
      verdict: str,
      deductions: [{source, type, column, severity, deduction, reason}],
      breakdown: {completeness, validity, consistency, uniqueness, anomaly},
      dimension_scores: {completeness: 0-100, ...}
    }
    """
    deductions = []
    dimension_costs = {
        "completeness": 0.0,
        "validity": 0.0,
        "consistency": 0.0,
        "uniqueness": 0.0,
        "anomaly": 0.0,
    }

    DIMENSION_MAP = {
        "missing_values":       "completeness",
        "duplicate_rows":       "uniqueness",
        "datatype_mismatch":    "validity",
        "range_violation":      "validity",
        "negative_value":       "validity",
        "regex_violation":      "validity",
        "invalid_category":     "validity",
        "date_order_violation": "consistency",
        "anomaly":              "anomaly",
    }

    # ── Validation issues ──────────────────────────────────────────────────
    for issue in issues:
        itype = issue.get("type", "unknown")
        sev = issue.get("severity", "info")
        col = issue.get("column", "ALL")
        pct = issue.get("pct", 0)

        weights = ISSUE_TYPE_WEIGHTS.get(itype, DEFAULT_ISSUE_WEIGHT)
        base_weight = weights.get(sev, 1)
        col_mult = _column_importance(col, user_importance)
        sev_mult = SEVERITY_MULTIPLIERS.get(sev, 1.0)

        # Deduction: base × severity_mult × col_importance × (1 + pct/100)
        deduction = round(base_weight * sev_mult * col_mult * (1 + pct / 100), 2)
        deduction = min(deduction, 25)  # cap per issue

        dimension = DIMENSION_MAP.get(itype, "validity")
        dimension_costs[dimension] += deduction

        deductions.append({
            "source": "rule",
            "type": itype,
            "column": col,
            "severity": sev,
            "deduction": deduction,
            "reason": issue.get("detail", ""),
        })

    # ── Anomalies ──────────────────────────────────────────────────────────
    for a in anomalies.get("per_column", []):
        sev = a.get("severity", "info")
        col = a.get("column", "")
        pct = a.get("outlier_pct", 0)
        weights = ISSUE_TYPE_WEIGHTS["anomaly"]
        base_weight = weights.get(sev, 1)
        col_mult = _column_importance(col, user_importance)
        deduction = round(base_weight * SEVERITY_MULTIPLIERS.get(sev, 1.0) * col_mult * (1 + pct / 100), 2)
        deduction = min(deduction, 15)
        dimension_costs["anomaly"] += deduction
        deductions.append({
            "source": "ml",
            "type": "anomaly",
            "column": col,
            "severity": sev,
            "deduction": deduction,
            "reason": f"{a['outlier_count']} statistical outliers ({a['method']})",
        })

    for method, mv in anomalies.get("multivariate", {}).items():
        if mv.get("count", 0) > 0:
            sev = mv.get("severity", "info")
            deduction = min(round(4 * SEVERITY_MULTIPLIERS.get(sev, 1.0) * (1 + mv["pct"] / 100), 2), 10)
            dimension_costs["anomaly"] += deduction
            deductions.append({
                "source": "ml",
                "type": f"multivariate_anomaly_{method}",
                "column": "MULTIVARIATE",
                "severity": sev,
                "deduction": deduction,
                "reason": f"{mv['count']} multivariate outliers ({method})",
            })

    total_deduction = sum(d["deduction"] for d in deductions)
    score = max(0, round(100 - total_deduction, 1))

    # Per-dimension scores (each starts at 100)
    dim_scores = {}
    for dim, cost in dimension_costs.items():
        dim_scores[dim] = max(0, round(100 - cost, 1))

    grade_map = [(90, "A"), (75, "B"), (60, "C"), (45, "D"), (0, "F")]
    grade = next(g for threshold, g in grade_map if score >= threshold)

    verdicts = {
        "A": "Excellent — data is production-ready with minimal issues.",
        "B": "Good — minor issues present, review warnings before use.",
        "C": "Fair — notable quality problems; remediation recommended.",
        "D": "Poor — significant data quality issues; use with caution.",
        "F": "Critical — data is unreliable; do not use without cleaning.",
    }

    return {
        "score": score,
        "grade": grade,
        "verdict": verdicts[grade],
        "total_deduction": round(total_deduction, 2),
        "deductions": sorted(deductions, key=lambda x: x["deduction"], reverse=True)[:20],
        "dimension_scores": dim_scores,
    }
