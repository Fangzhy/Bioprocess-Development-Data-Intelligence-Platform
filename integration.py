"""Pure data preparation functions, independent of the Streamlit interface."""
from io import BytesIO
import sqlite3

import numpy as np
import pandas as pd

SCHEMAS = {
    "batch_metadata": "batch_id cell_line media_type media_lot bioreactor_scale seed_density experiment_date operator".split(),
    "process_timeseries": "batch_id time_hr temperature pH DO agitation air_flow O2_flow CO2_flow feed_rate sensor_glucose sensor_lactate".split(),
    "offline_assays": "batch_id time_hr viable_cell_density viability glucose lactate ammonia product_titer".split(),
    "final_quality": "batch_id final_titer purity aggregation glycosylation_metric yield".split(),
}
TEXT = set("batch_id cell_line media_type media_lot experiment_date operator".split())
REPORT_COLUMNS = ["dataset", "severity", "issue", "column", "count", "examples"]
MAX_ROWS = 100_000
MAX_BYTES = 10 * 1024 * 1024


def read_upload(content, filename):
    """Read a bounded CSV or the first worksheet of an XLSX workbook."""
    if len(content) > MAX_BYTES:
        raise ValueError("File exceeds the 10 MB limit.")
    try:
        if filename.lower().endswith(".csv"):
            frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False, nrows=MAX_ROWS + 1)
        elif filename.lower().endswith(".xlsx"):
            frame = pd.read_excel(BytesIO(content), dtype=str, keep_default_na=False,
                                  engine="openpyxl", nrows=MAX_ROWS + 1)
        else:
            raise ValueError("Use a CSV or .xlsx file.")
    except Exception as error:
        raise ValueError(f"Unable to read {filename}: {error}") from error
    if len(frame) > MAX_ROWS:
        raise ValueError(f"File exceeds the {MAX_ROWS:,} row limit.")
    return frame


def validate(tables, duration=336, process_step=4, assay_step=24):
    """Normalize parseable types on copies; report problems without imputing values."""
    prepared, issues = {}, []

    def add(name, severity, issue, column, count, examples=""):
        if count:
            issues.append([name, severity, issue, column, int(count), str(examples)])

    for name, columns in SCHEMAS.items():
        if name not in tables:
            add(name, "error", "missing_table", "", 1)
            continue
        frame = tables[name].copy(deep=True).reset_index(drop=True)
        missing = set(columns) - set(frame.columns)
        add(name, "error", "missing_columns", "", len(missing), sorted(missing))
        extra = set(frame.columns) - set(columns)
        add(name, "warning", "extra_columns", "", len(extra), sorted(extra))
        add(name, "error", "empty_table", "", int(frame.empty))
        for column in set(columns) & set(frame.columns):
            raw = frame[column].replace(r"^\s*$", np.nan, regex=True)
            nulls = raw.isna()
            keys = column in ("batch_id", "time_hr")
            add(name, "error" if keys else "warning", "missing_value", column, nulls.sum(),
                (np.flatnonzero(nulls)[:5] + 2).tolist())
            if column not in TEXT:
                converted = pd.to_numeric(raw, errors="coerce")
                invalid = raw.notna() & (converted.isna() | ~np.isfinite(converted))
                add(name, "error", "invalid_numeric", column, invalid.sum(), raw[invalid].head().tolist())
                # Keep invalid text visible in the working copy; SQL is blocked.
                frame[column] = raw if invalid.any() else converted
                if invalid.any():
                    continue
                bad = converted < 0
                if column in ("DO", "viability", "purity", "aggregation", "glycosylation_metric", "yield"):
                    bad |= converted > 100
                if column == "pH":
                    bad |= converted > 14
                if column in ("bioreactor_scale", "seed_density"):
                    bad |= converted <= 0
                if column == "time_hr":
                    bad |= (converted > duration) | (converted % 1 != 0)
                add(name, "error" if keys else "warning", "out_of_range", column, bad.sum(), raw[bad].head().tolist())
            elif column == "experiment_date":
                bad = raw.notna() & pd.to_datetime(raw, format="%Y-%m-%d", errors="coerce").isna()
                add(name, "error", "invalid_date", column, bad.sum(), raw[bad].head().tolist())
                frame[column] = raw
            else:
                frame[column] = raw.astype("string")
                padded = frame[column].notna() & frame[column].ne(frame[column].str.strip())
                add(name, "error", "surrounding_whitespace", column, padded.sum())
        keys = ["batch_id", "time_hr"] if "time_hr" in columns else ["batch_id"]
        exact = frame.duplicated()
        add(name, "error", "exact_duplicate", "", exact.sum())
        if set(keys).issubset(frame.columns):
            distinct = frame.drop_duplicates()
            conflicts = distinct.duplicated(keys, keep=False)
            add(name, "error", "conflicting_key", ", ".join(keys), conflicts.sum(), distinct.loc[conflicts, keys].head().to_dict("records"))
        prepared[name] = frame

    parent = prepared.get("batch_metadata", pd.DataFrame())
    if "batch_id" in parent:
        ids = set(parent.batch_id.dropna())
        for name, frame in prepared.items():
            if name == "batch_metadata" or "batch_id" not in frame:
                continue
            orphan = frame.batch_id.notna() & ~frame.batch_id.isin(ids)
            add(name, "error", "unknown_batch", "batch_id", orphan.sum(), frame.loc[orphan, "batch_id"].head().tolist())
            absent = ids - set(frame.batch_id.dropna())
            add(name, "warning", "missing_batch_records", "batch_id", len(absent), sorted(absent)[:5])
            if "time_hr" in frame and pd.api.types.is_numeric_dtype(frame.time_hr):
                step = process_step if name == "process_timeseries" else assay_step
                expected = set(range(0, duration + 1, step))
                groups = {batch: set(group.time_hr.dropna()) for batch, group in frame.groupby("batch_id")}
                gaps = {batch: len(expected - groups.get(batch, set())) for batch in ids}
                add(name, "warning", "missing_timepoints", "time_hr", sum(gaps.values()),
                    {batch: gaps[batch] for batch in sorted(gaps) if gaps[batch] > 0})
                off_grid = frame.time_hr.notna() & ~frame.time_hr.isin(expected)
                add(name, "warning", "off_grid_time", "time_hr", off_grid.sum())
    return prepared, pd.DataFrame(issues, columns=REPORT_COLUMNS)


def clean_tables(tables, remove_duplicates=False, exclude_unknown=False):
    """Return new tables and a row-level removal log; never modify inputs."""
    result, changes = {}, []
    parent = tables.get("batch_metadata", pd.DataFrame())
    ids = set(parent.batch_id.dropna()) if "batch_id" in parent else None
    for name, source in tables.items():
        frame = source.copy(deep=True)
        duplicate = frame.duplicated() if remove_duplicates else pd.Series(False, index=frame.index)
        unknown = pd.Series(False, index=frame.index)
        if exclude_unknown and name != "batch_metadata" and "batch_id" in frame and ids is not None:
            unknown = frame.batch_id.notna() & ~frame.batch_id.isin(ids)
        for position in np.flatnonzero(duplicate | unknown):
            row = frame.iloc[position]
            changes.append(dict(dataset=name, source_row=int(position + 2), batch_id=row.get("batch_id", ""),
                                time_hr=row.get("time_hr", ""), action="remove_exact_duplicate" if duplicate.iloc[position] else "exclude_unknown_batch"))
        result[name] = frame.loc[~(duplicate | unknown)].reset_index(drop=True)
    return result, pd.DataFrame(changes, columns=["dataset", "source_row", "batch_id", "time_hr", "action"])


BATCH_QUERY = '''SELECT b.*, q.final_titer, q.purity, q.aggregation,
       q.glycosylation_metric, q."yield"
FROM batch_metadata AS b
LEFT JOIN final_quality AS q ON b.batch_id = q.batch_id
ORDER BY b.batch_id'''


def integrate_sql(tables, **validation_settings):
    """Build a private, ephemeral constrained SQLite database and batch join."""
    prepared, report = validate(tables, **validation_settings)
    if (report.severity == "error").any():
        raise ValueError("Resolve the blocking quality errors before SQL integration.")
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        for name, columns in SCHEMAS.items():
            keys = ["batch_id", "time_hr"] if "time_hr" in columns else ["batch_id"]
            declarations = [f'"{column}" {"TEXT" if column in TEXT else "REAL"}' + (" NOT NULL" if column in keys else "") for column in columns]
            declarations.append("PRIMARY KEY (" + ", ".join(f'"{key}"' for key in keys) + ")")
            if name != "batch_metadata":
                declarations.append('FOREIGN KEY (batch_id) REFERENCES batch_metadata(batch_id)')
            connection.execute(f'CREATE TABLE "{name}" ({", ".join(declarations)})')
            rows = prepared[name][columns].astype(object).where(prepared[name][columns].notna(), None)
            connection.executemany(f'INSERT INTO "{name}" VALUES ({", ".join("?" for _ in columns)})', rows.itertuples(index=False, name=None))
        batch = pd.read_sql_query(BATCH_QUERY, connection)
        if len(batch) != len(prepared["batch_metadata"]):
            raise ValueError("Batch join unexpectedly changed the number of metadata rows.")
        return batch
    finally:
        connection.close()
