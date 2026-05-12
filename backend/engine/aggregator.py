
from typing import Any

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def aggregate_issues(
    validation_issues: list[dict],
    anomalies: dict,
) -> list[dict]:
    
    all_issues = list(validation_issues)  # already tagged source: "rule"

    # Flatten per-column anomalies into issue shape
    for a in anomalies.get("per_column", []):
        all_issues.append({
            "type": "anomaly",
            "severity": a["severity"],
            "column": a["column"],
            "detail": (
                f"{a['outlier_count']} statistical outliers ({a['method']}) — "
                f"{a['outlier_pct']}% of rows. "
                f"Sample values: {a['outlier_values'][:5]}"
            ),
            "count": a["outlier_count"],
            "pct": a["outlier_pct"],
            "affected_rows": a.get("outlier_indices", [])[:20],
            "source": "ml",
        })

    for method, mv in anomalies.get("multivariate", {}).items():
        if mv.get("count", 0) > 0:
            all_issues.append({
                "type": f"multivariate_anomaly",
                "severity": mv["severity"],
                "column": "MULTIVARIATE",
                "detail": (
                    f"{mv['count']} rows flagged as multivariate anomalies "
                    f"by {method.replace('_', ' ')} ({mv['pct']}% of data)"
                ),
                "count": mv["count"],
                "pct": mv["pct"],
                "affected_rows": mv.get("indices", [])[:20],
                "source": "ml",
            })

    # Sort: severity first, then count descending
    all_issues.sort(key=lambda x: (
        SEVERITY_ORDER.get(x.get("severity"), 3),
        -x.get("count", 0)
    ))

    # Add rank and issue_id
    for i, issue in enumerate(all_issues):
        issue["rank"] = i + 1
        issue["id"] = f"issue_{i+1}"

    return all_issues


def summary_stats(all_issues: list[dict]) -> dict:
    counts = {"critical": 0, "warning": 0, "info": 0}
    by_source = {"rule": 0, "ml": 0}
    by_type: dict[str, int] = {}

    for issue in all_issues:
        sev = issue.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
        src = issue.get("source", "rule")
        by_source[src] = by_source.get(src, 0) + 1
        t = issue.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total": len(all_issues),
        "by_severity": counts,
        "by_source": by_source,
        "by_type": by_type,
    }
