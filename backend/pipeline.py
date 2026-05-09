
from backend.engine.ingestion import load_csv, infer_schema
from backend.engine.profiling import profile_dataframe
from backend.engine.validation import run_validation
from backend.engine.anomaly import detect_anomalies
from backend.engine.aggregator import aggregate_issues, summary_stats
from backend.engine.scoring import compute_score
from backend.engine.report import generate_report


def run_pipeline(
    filename: str,
    content: bytes,
    user_rules: dict = None,
    generate_report_flag: bool = False,
) -> dict:
    user_rules = user_rules or {}

    df = load_csv(content)

    schema = infer_schema(df)

    profile = profile_dataframe(df, schema)

    validation_issues = run_validation(df, schema, user_rules)

    anomalies = detect_anomalies(df, schema)

    all_issues = aggregate_issues(validation_issues, anomalies)
    stats = summary_stats(all_issues)

    user_importance = {
        col: cfg.get("importance")
        for col, cfg in user_rules.get("columns", {}).items()
        if cfg.get("importance")
    }
    score = compute_score(
        issues=validation_issues,
        anomalies=anomalies,
        total_rows=len(df),
        total_cols=len(df.columns),
        user_importance=user_importance or None,
    )

    ai_report = None
    if generate_report_flag:
        ai_report = generate_report(
            filename=filename,
            profile=profile,
            issues=all_issues,
            anomalies=anomalies,
            score=score,
        )

    return {
        "filename": filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "schema": schema,
        "profile": profile,
        "issues": all_issues,
        "issue_stats": stats,
        "anomalies": anomalies,
        "score": score,
        "ai_report": ai_report,
    }