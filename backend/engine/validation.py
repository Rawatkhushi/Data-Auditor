
import pandas as pd
import numpy as np
from typing import Any


def _issue(type_: str, severity: str, column: str, detail: str,
           count: int, pct: float, rows: list = None) -> dict:
    return {
        "type": type_,
        "severity": severity,
        "column": column,
        "detail": detail,
        "count": count,
        "pct": round(pct, 2),
        "affected_rows": (rows or [])[:20],  # cap for payload size
        "source": "rule",
    }


def check_missing(df: pd.DataFrame, col: str, threshold_pct: float = 5.0) -> list[dict]:
    
    issues = []
    null_count = int(df[col].isna().sum())
    null_pct = null_count / len(df) * 100
    if null_pct > threshold_pct:
        sev = "critical" if null_pct > 40 else "warning" if null_pct > 15 else "info"
        issues.append(_issue(
            "missing_values", sev, col,
            f"{null_pct:.1f}% null values ({null_count}/{len(df)} rows). Threshold: {threshold_pct}%",
            null_count, null_pct,
            list(df[df[col].isna()].index[:20])
        ))
    return issues


def check_duplicates(df: pd.DataFrame) -> list[dict]:
    dup_mask = df.duplicated(keep="first")
    dup_count = int(dup_mask.sum())
    if dup_count:
        pct = dup_count / len(df) * 100
        sev = "critical" if pct > 10 else "warning"
        return [_issue("duplicate_rows", sev, "ALL",
                       f"{dup_count} fully duplicate rows ({pct:.1f}% of dataset)",
                       dup_count, pct, list(df[dup_mask].index[:20]))]
    return []


def check_dtype_mismatch(df: pd.DataFrame, col: str, expected_type: str) -> list[dict]:
    """Detect values that don't parse as expected_type."""
    issues = []
    series = df[col].dropna()
    if expected_type == "numeric":
        bad = series[pd.to_numeric(series, errors="coerce").isna()]
        if len(bad):
            pct = len(bad) / len(df) * 100
            issues.append(_issue(
                "datatype_mismatch", "warning", col,
                f"{len(bad)} non-numeric values in numeric column (e.g. {bad.head(3).tolist()})",
                len(bad), pct, list(bad.index[:20])
            ))
    elif expected_type == "date":
        bad = series[pd.to_datetime(series, errors="coerce").isna()]
        if len(bad):
            pct = len(bad) / len(df) * 100
            issues.append(_issue(
                "datatype_mismatch", "warning", col,
                f"{len(bad)} unparseable date values (e.g. {bad.head(3).tolist()})",
                len(bad), pct, list(bad.index[:20])
            ))
    return issues


def check_range(df: pd.DataFrame, col: str,
                min_val: float = None, max_val: float = None) -> list[dict]:
    
    issues = []
    numeric = pd.to_numeric(df[col], errors="coerce")
    if min_val is not None:
        bad = df[numeric < min_val]
        if len(bad):
            pct = len(bad) / len(df) * 100
            issues.append(_issue(
                "range_violation", "critical", col,
                f"{len(bad)} values below minimum {min_val} (e.g. {numeric[bad.index].head(3).tolist()})",
                len(bad), pct, list(bad.index[:20])
            ))
    if max_val is not None:
        bad = df[numeric > max_val]
        if len(bad):
            pct = len(bad) / len(df) * 100
            issues.append(_issue(
                "range_violation", "critical", col,
                f"{len(bad)} values above maximum {max_val}",
                len(bad), pct, list(bad.index[:20])
            ))
    return issues


def check_regex(df: pd.DataFrame, col: str, pattern: str) -> list[dict]:
    
    series = df[col].dropna().astype(str)
    bad_mask = ~series.str.match(pattern, na=False)
    bad = series[bad_mask]
    if len(bad):
        pct = len(bad) / len(df) * 100
        return [_issue(
            "regex_violation", "warning", col,
            f"{len(bad)} values don't match pattern '{pattern}'",
            len(bad), pct, list(bad.index[:20])
        )]
    return []


def check_allowed_values(df: pd.DataFrame, col: str, allowed: list) -> list[dict]:
    series = df[col].dropna().astype(str)
    bad = series[~series.isin([str(a) for a in allowed])]
    if len(bad):
        pct = len(bad) / len(df) * 100
        return [_issue(
            "invalid_category", "warning", col,
            f"{len(bad)} values not in allowed set {allowed[:5]}",
            len(bad), pct, list(bad.index[:20])
        )]
    return []


def check_date_order(df: pd.DataFrame, start_col: str, end_col: str) -> list[dict]:
    
    issues = []
    if start_col not in df.columns or end_col not in df.columns:
        return issues
    s = pd.to_datetime(df[start_col], errors="coerce")
    e = pd.to_datetime(df[end_col], errors="coerce")
    bad = df[(s.notna()) & (e.notna()) & (s > e)]
    if len(bad):
        pct = len(bad) / len(df) * 100
        issues.append(_issue(
            "date_order_violation", "critical",
            f"{start_col} → {end_col}",
            f"{len(bad)} rows where {start_col} > {end_col}",
            len(bad), pct, list(bad.index[:20])
        ))
    return issues


def check_negative_in_positive_col(df: pd.DataFrame, col: str) -> list[dict]:
    numeric = pd.to_numeric(df[col], errors="coerce")
    bad = df[numeric < 0]
    if len(bad):
        pct = len(bad) / len(df) * 100
        sev = "critical"
        return [_issue(
            "negative_value", sev, col,
            f"{len(bad)} negative values (column '{col}' expected ≥ 0)",
            len(bad), pct, list(bad.index[:20])
        )]
    return []


def run_validation(df: pd.DataFrame, schema: dict, user_rules: dict = None) -> list[dict]:
    """
    user_rules: {
      "columns": {
        "age": {"min": 0, "max": 120, "null_threshold": 5},
        "email": {"regex": r"^[^@]+@[^@]+\.[^@]+$"},
        "status": {"allowed_values": ["active", "inactive"]},
        ...
      },
      "cross_column": [
        {"type": "date_order", "start": "start_date", "end": "end_date"},
        ...
      ],
      "global_null_threshold": 10
    }
    """
    user_rules = user_rules or {}
    col_rules = user_rules.get("columns", {})
    cross_rules = user_rules.get("cross_column", [])
    global_null_thresh = user_rules.get("global_null_threshold", 20)

    issues = []

    # Row-level
    issues += check_duplicates(df)

    # Column-level
    for col in df.columns:
        col_cfg = col_rules.get(col, {})
        inferred = schema.get(col, "text")

        null_thresh = col_cfg.get("null_threshold", global_null_thresh)
        issues += check_missing(df, col, null_thresh)

        issues += check_dtype_mismatch(df, col, inferred)

        if "min" in col_cfg or "max" in col_cfg:
            issues += check_range(df, col, col_cfg.get("min"), col_cfg.get("max"))
        elif inferred == "numeric":
            col_lower = col.lower()
            if any(k in col_lower for k in ["age", "salary", "price", "amount", "score", "count", "qty", "quantity", "revenue"]):
                issues += check_negative_in_positive_col(df, col)

        if "regex" in col_cfg:
            issues += check_regex(df, col, col_cfg["regex"])

        if "allowed_values" in col_cfg:
            issues += check_allowed_values(df, col, col_cfg["allowed_values"])

    for rule in cross_rules:
        if rule.get("type") == "date_order":
            issues += check_date_order(df, rule["start"], rule["end"])

    if not cross_rules:
        date_cols = [c for c in df.columns if schema.get(c) == "date"]
        start_cols = [c for c in date_cols if any(k in c.lower() for k in ["start", "from", "created", "begin"])]
        end_cols   = [c for c in date_cols if any(k in c.lower() for k in ["end", "to", "updated", "finish", "close"])]
        for s in start_cols:
            for e in end_cols:
                issues += check_date_order(df, s, e)

    return issues
