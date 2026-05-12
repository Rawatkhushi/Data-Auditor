
import pandas as pd
import numpy as np
from typing import Any


def profile_column(series: pd.Series, inferred_type: str) -> dict:
    total = len(series)
    null_count = int(series.isna().sum())
    non_null = series.dropna()
    unique_count = int(non_null.nunique())

    base = {
        "column": series.name,
        "inferred_type": inferred_type,
        "total": total,
        "null_count": null_count,
        "null_pct": round(null_count / total * 100, 2) if total else 0,
        "unique_count": unique_count,
        "unique_pct": round(unique_count / len(non_null) * 100, 2) if len(non_null) else 0,
        "sample_values": non_null.head(5).tolist(),
    }

    if inferred_type == "numeric":
        numeric = pd.to_numeric(non_null, errors="coerce").dropna()
        if len(numeric):
            q1 = float(numeric.quantile(0.25))
            q3 = float(numeric.quantile(0.75))
            base.update({
                "min": round(float(numeric.min()), 4),
                "max": round(float(numeric.max()), 4),
                "mean": round(float(numeric.mean()), 4),
                "median": round(float(numeric.median()), 4),
                "std": round(float(numeric.std()), 4),
                "q1": round(q1, 4),
                "q3": round(q3, 4),
                "iqr": round(q3 - q1, 4),
                "skewness": round(float(numeric.skew()), 4),
                "kurtosis": round(float(numeric.kurtosis()), 4),
                # histogram: 10 buckets for frontend chart
                "histogram": _histogram(numeric, bins=10),
            })

    elif inferred_type == "date":
        dates = pd.to_datetime(non_null, errors="coerce").dropna()
        if len(dates):
            base.update({
                "min_date": str(dates.min().date()),
                "max_date": str(dates.max().date()),
                "date_range_days": int((dates.max() - dates.min()).days),
            })

    elif inferred_type in ("categorical", "text"):
        top_vals = non_null.value_counts().head(10)
        base.update({
            "top_values": [
                {"value": str(k), "count": int(v), "pct": round(v / len(non_null) * 100, 1)}
                for k, v in top_vals.items()
            ],
            "avg_length": round(float(non_null.astype(str).str.len().mean()), 1),
        })

    return base


def _histogram(series: pd.Series, bins: int = 10) -> list[dict]:
    counts, edges = np.histogram(series.dropna(), bins=bins)
    return [
        {"bucket": f"{round(float(edges[i]),2)}–{round(float(edges[i+1]),2)}", "count": int(counts[i])}
        for i in range(len(counts))
    ]


def profile_dataframe(df: pd.DataFrame, schema: dict) -> list[dict]:
    return [profile_column(df[col], schema.get(col, "text")) for col in df.columns]
