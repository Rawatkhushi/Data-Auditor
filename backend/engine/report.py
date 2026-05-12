
import json
import textwrap
from typing import Optional, Generator


# ── Public API ─────────────────────────────────────────────────────────────

def generate_report(
    filename: str,
    profile: list[dict],
    issues: list[dict],
    anomalies: dict,
    score: dict,
    drift: Optional[dict] = None,
) -> str:
    """
    Synchronous report generation.
    Returns complete report text as a single string.
    """
    return _build_report(filename, profile, issues, anomalies, score, drift)


def stream_report(
    filename: str,
    profile: list[dict],
    issues: list[dict],
    anomalies: dict,
    score: dict,
    drift: Optional[dict] = None,
) -> Generator[str, None, None]:
    """
    Stream report generation using Server-Sent Events (SSE).
    Splits generated report into small chunks and yields SSE-formatted strings.

    Usage in FastAPI:
        @app.post("/audit/report/stream")
        async def stream_audit_report(request: StreamReportRequest):
            def generate():
                for chunk in stream_report(...):
                    yield chunk
            return StreamingResponse(generate(), media_type="text/event-stream")
    """
    report = _build_report(filename, profile, issues, anomalies, score, drift)

    # Split into ~80-char chunks to simulate streaming
    chunk_size = 80
    for i in range(0, len(report), chunk_size):
        chunk = report[i : i + chunk_size]
        escaped = chunk.replace("\n", "\\n")
        yield f'data: {json.dumps({"chunk": escaped})}\n\n'


# ── Report Builder ─────────────────────────────────────────────────────────

def _build_report(
    filename: str,
    profile: list[dict],
    issues: list[dict],
    anomalies: dict,
    score: dict,
    drift: Optional[dict],
) -> str:
    sections = [
        _section_executive_summary(filename, profile, issues, score),
        _section_critical_findings(issues),
        _section_dimension_analysis(score),
        _section_anomaly_summary(anomalies),
        _section_drift(drift),
        _section_recommended_actions(issues, anomalies, score),
    ]
    return "\n\n".join(s for s in sections if s)


# ── Section Builders ───────────────────────────────────────────────────────

def _section_executive_summary(
    filename: str, profile: list[dict], issues: list[dict], score: dict
) -> str:
    total_rows = profile[0]["total"] if profile else 0
    total_cols = len(profile)
    sc = score["score"]
    grade = score["grade"]
    verdict = score["verdict"]
    critical_count = sum(1 for i in issues if i.get("severity") == "critical")
    warning_count = sum(1 for i in issues if i.get("severity") == "warning")

    null_cols = [p["column"] for p in profile if p.get("null_pct", 0) > 20]
    null_note = (
        f" Columns with significant missing data include: {', '.join(null_cols[:3])}."
        if null_cols
        else ""
    )

    lines = [
        "## Executive Summary",
        "",
        (
            f"Dataset '{filename}' contains {total_rows:,} rows across {total_cols} columns "
            f"and received a quality score of {sc}/100 (Grade {grade}). {verdict}"
        ),
        (
            f"The audit identified {critical_count} critical issue(s) and {warning_count} warning(s) "
            f"that require attention before this data is used in production.{null_note}"
        ),
    ]
    return "\n".join(lines)


def _section_critical_findings(issues: list[dict]) -> str:
    critical = [i for i in issues if i.get("severity") == "critical"]
    warnings = [i for i in issues if i.get("severity") == "warning"]
    top = (critical + warnings)[:5]

    if not top:
        return "## Critical Findings\n\nNo critical issues or warnings detected. The dataset appears clean."

    lines = ["## Critical Findings", ""]
    for item in top:
        badge = "🔴" if item["severity"] == "critical" else "🟡"
        col = item.get("column", "ALL")
        lines.append(f"{badge} [{item['severity'].upper()}] {col} — {item['detail']}")

    return "\n".join(lines)


def _section_dimension_analysis(score: dict) -> str:
    dims = score.get("dimension_scores", {})
    dim_labels = {
        "completeness": "Completeness",
        "validity":     "Validity",
        "consistency":  "Consistency",
        "uniqueness":   "Uniqueness",
        "anomaly":      "Anomaly",
    }

    def grade_label(val: float) -> str:
        if val >= 90: return "Excellent"
        if val >= 75: return "Good"
        if val >= 60: return "Fair"
        if val >= 45: return "Poor"
        return "Critical"

    lines = ["## Dimension Analysis", ""]
    for key, label in dim_labels.items():
        val = dims.get(key, 100.0)
        lines.append(f"- **{label}** ({val}/100): {grade_label(val)}")

    return "\n".join(lines)


def _section_anomaly_summary(anomalies: dict) -> str:
    per_col = anomalies.get("per_column", [])
    multi = anomalies.get("multivariate", {})
    iso = multi.get("isolation_forest", {})
    lof = multi.get("lof", {})

    if not per_col and not iso.get("count") and not lof.get("count"):
        return "## Anomaly Summary\n\nNo statistical anomalies detected across any column."

    lines = ["## Anomaly Summary", ""]

    if per_col:
        lines.append(f"Per-column statistical anomalies were detected in {len(per_col)} column(s):")
        for a in per_col[:5]:
            lines.append(
                f"  - **{a['column']}**: {a['outlier_count']} outlier(s) "
                f"({a['outlier_pct']}%) via {a['method']}"
            )

    iso_count = iso.get("count", 0)
    lof_count = lof.get("count", 0)
    if iso_count or lof_count:
        lines.append(
            f"Multivariate anomaly detection flagged {iso_count} row(s) via Isolation Forest "
            f"and {lof_count} row(s) via Local Outlier Factor."
        )

    return "\n".join(lines)


def _section_drift(drift: Optional[dict]) -> str:
    if not drift:
        return ""  # Omit section entirely if no drift data

    drifted = drift.get("drifted_columns", 0)
    total = drift.get("compared_columns", 0)
    overall = drift.get("overall_drift_score", "N/A")

    lines = [
        "## Data Drift",
        "",
        f"Compared against reference dataset: {drifted}/{total} column(s) show significant drift "
        f"(overall drift score: {overall}).",
    ]

    top_drifted = [c for c in drift.get("columns", []) if c.get("drift_detected")][:3]
    for c in top_drifted:
        lines.append(f"  - **{c['column']}**: {c.get('drift_level', 'unknown')} drift (PSI: {c.get('psi', 'N/A')})")

    return "\n".join(lines)


def _section_recommended_actions(
    issues: list[dict], anomalies: dict, score: dict
) -> str:
    actions: list[str] = []

    # Missing values
    missing = [i for i in issues if i.get("type") == "missing_values" and i.get("severity") in ("critical", "warning")]
    if missing:
        cols = ", ".join(i["column"] for i in missing[:3])
        actions.append(
            f"Address missing values in high-null columns ({cols}): "
            "impute with median/mode for numeric/categorical fields, or remove rows exceeding 40% nulls."
        )

    # Duplicates
    dups = [i for i in issues if i.get("type") == "duplicate_rows"]
    if dups:
        actions.append(
            f"Remove {dups[0]['count']} duplicate rows identified in the dataset "
            "to prevent double-counting in analytics pipelines."
        )

    # Type mismatches
    type_issues = [i for i in issues if i.get("type") == "datatype_mismatch"]
    if type_issues:
        cols = ", ".join(i["column"] for i in type_issues[:3])
        actions.append(
            f"Correct datatype mismatches in column(s) {cols}: "
            "cast to the appropriate type or investigate upstream data entry errors."
        )

    # Range / negative violations
    range_issues = [i for i in issues if i.get("type") in ("range_violation", "negative_value")]
    if range_issues:
        cols = ", ".join(i["column"] for i in range_issues[:3])
        actions.append(
            f"Investigate out-of-range or negative values in {cols}: "
            "apply domain-level constraints at ingestion or flag for manual review."
        )

    # Regex violations
    regex_issues = [i for i in issues if i.get("type") == "regex_violation"]
    if regex_issues:
        cols = ", ".join(i["column"] for i in regex_issues[:2])
        actions.append(
            f"Fix format violations in {cols}: enforce input validation at the source system."
        )

    # Anomalies
    if anomalies.get("per_column"):
        actions.append(
            "Review statistical outliers flagged per-column: determine whether they represent "
            "legitimate edge cases or erroneous entries before including in model training."
        )

    multi = anomalies.get("multivariate", {})
    if multi.get("isolation_forest", {}).get("count", 0) > 0:
        actions.append(
            "Investigate multivariate anomalies from Isolation Forest: these rows exhibit "
            "unusual combinations of feature values and may distort aggregate statistics."
        )

    # Low score catch-all
    if score["score"] < 60 and len(actions) < 3:
        actions.append(
            "Conduct a full data lineage review — the low quality score suggests systemic "
            "issues in upstream data collection or ETL processes."
        )

    if not actions:
        actions.append(
            "No immediate remediation required. Schedule a routine data quality review "
            "in 30 days to monitor for drift or new issues."
        )

    lines = ["## Recommended Actions", ""]
    for idx, action in enumerate(actions[:6], start=1):
        lines.append(f"{idx}. {action}")

    return "\n".join(lines)