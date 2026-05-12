
import pandas as pd
import numpy as np
from typing import Optional


def _zscore_outliers(series: pd.Series, threshold: float = 3.0) -> np.ndarray:
    mean = series.mean()
    std = series.std()
    if std == 0:
        return np.array([], dtype=int)
    z = np.abs((series - mean) / std)
    return series.index[z > threshold].tolist()


def _iqr_outliers(series: pd.Series, k: float = 1.5) -> list:
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return []
    lower, upper = q1 - k * iqr, q3 + k * iqr
    return series.index[(series < lower) | (series > upper)].tolist()


def _isolation_forest(df_numeric: pd.DataFrame, contamination: float = 0.05) -> np.ndarray:
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.impute import SimpleImputer
        imp = SimpleImputer(strategy="median")
        X = imp.fit_transform(df_numeric)
        clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
        preds = clf.fit_predict(X)
        return df_numeric.index[preds == -1].tolist()
    except Exception:
        return []


def _lof(df_numeric: pd.DataFrame, contamination: float = 0.05) -> list:
    try:
        from sklearn.neighbors import LocalOutlierFactor
        from sklearn.impute import SimpleImputer
        imp = SimpleImputer(strategy="median")
        X = imp.fit_transform(df_numeric)
        clf = LocalOutlierFactor(n_neighbors=min(20, len(X) - 1), contamination=contamination)
        preds = clf.fit_predict(X)
        return df_numeric.index[preds == -1].tolist()
    except Exception:
        return []


def detect_anomalies(df: pd.DataFrame, schema: dict,
                     methods: list[str] = None,
                     contamination: float = 0.05) -> dict:
    """
    Returns:
    {
      "per_column": [
        {column, method, outlier_count, outlier_pct, severity,
         outlier_indices, outlier_values, stats}
      ],
      "multivariate": {
        "isolation_forest": {count, pct, indices},
        "lof": {count, pct, indices}
      }
    }
    """
    if methods is None:
        methods = ["zscore", "iqr", "isolation_forest", "lof"]

    numeric_cols = [c for c in df.columns if schema.get(c) == "numeric"]
    results = {"per_column": [], "multivariate": {}}

    # ── Per-column: Z-score + IQR ──────────────────────────────────────────
    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 10:
            continue

        outlier_idx = set()
        used_methods = []

        if "zscore" in methods:
            z_idx = _zscore_outliers(series)
            outlier_idx.update(z_idx)
            if z_idx:
                used_methods.append("z-score")

        if "iqr" in methods:
            iqr_idx = _iqr_outliers(series)
            outlier_idx.update(iqr_idx)
            if iqr_idx:
                used_methods.append("IQR")

        if not outlier_idx:
            continue

        outlier_idx = sorted(outlier_idx)
        outlier_vals = series.loc[[i for i in outlier_idx if i in series.index]].round(4).tolist()
        count = len(outlier_idx)
        pct = round(count / len(df) * 100, 2)
        sev = "critical" if pct > 10 else "warning" if pct > 3 else "info"

        results["per_column"].append({
            "column": col,
            "method": " + ".join(used_methods) if used_methods else "z-score/IQR",
            "outlier_count": count,
            "outlier_pct": pct,
            "severity": sev,
            "outlier_indices": outlier_idx[:30],
            "outlier_values": outlier_vals[:10],
            "stats": {
                "mean": round(float(series.mean()), 4),
                "std": round(float(series.std()), 4),
                "q1": round(float(series.quantile(0.25)), 4),
                "q3": round(float(series.quantile(0.75)), 4),
            }
        })

    # ── Multivariate: Isolation Forest + LOF ─────────────────────────────
    if len(numeric_cols) >= 2 and len(df) >= 20:
        df_num = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

        if "isolation_forest" in methods:
            idx = _isolation_forest(df_num, contamination)
            count = len(idx)
            results["multivariate"]["isolation_forest"] = {
                "count": count,
                "pct": round(count / len(df) * 100, 2),
                "indices": idx[:30],
                "severity": "warning" if count > 0 else "info",
            }

        if "lof" in methods:
            idx = _lof(df_num, contamination)
            count = len(idx)
            results["multivariate"]["lof"] = {
                "count": count,
                "pct": round(count / len(df) * 100, 2),
                "indices": idx[:30],
                "severity": "warning" if count > 0 else "info",
            }

    return results
