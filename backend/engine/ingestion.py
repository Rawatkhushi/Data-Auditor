
import io
import pandas as pd
import numpy as np
from typing import Optional


def load_csv(content: bytes, chunk_size: Optional[int] = None) -> pd.DataFrame:
   
    encodings = ["utf-8", "latin-1", "cp1252", "utf-16"]
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(
                io.BytesIO(content),
                encoding=enc,
                low_memory=False,
                nrows=chunk_size,
                dtype=str,          # load everything as str first; profiler will infer
                keep_default_na=False,
            )
            break
        except (UnicodeDecodeError, Exception):
            continue

    if df is None:
        raise ValueError("Could not decode file with any supported encoding.")

    # Normalise column names: strip whitespace
    df.columns = [c.strip() for c in df.columns]

    # Replace common null-like strings with actual NaN
    null_strings = {"", "null", "NULL", "None", "NONE", "nan", "NaN", "N/A", "n/a", "NA", "#N/A"}
    df = df.replace(null_strings, np.nan)

    return df


def infer_schema(df: pd.DataFrame) -> dict:
    
    schema = {}
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            schema[col] = "unknown"
            continue

        # Try numeric
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() / len(series) > 0.85:
            schema[col] = "numeric"
            continue

        # Try date
        try:
            parsed = pd.to_datetime(series, infer_datetime_format=True, errors="coerce")
            if parsed.notna().sum() / len(series) > 0.80:
                schema[col] = "date"
                continue
        except Exception:
            pass

        # Boolean-ish
        uniq = set(series.str.lower().unique())
        if uniq <= {"true", "false", "yes", "no", "0", "1", "t", "f", "y", "n"}:
            schema[col] = "boolean"
            continue

        # Cardinality heuristic: low unique → categorical
        if series.nunique() / len(series) < 0.10:
            schema[col] = "categorical"
        else:
            schema[col] = "text"

    return schema
