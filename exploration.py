"""Filtering, descriptive summaries, and charts for prepared batch data."""
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative


VARIABLES = {
    "Temperature": ("process_timeseries", "temperature", "°C"),
    "pH": ("process_timeseries", "pH", "dimensionless"),
    "Dissolved oxygen": ("process_timeseries", "DO", "% air saturation"),
    "Agitation": ("process_timeseries", "agitation", "rpm"),
    "Air flow": ("process_timeseries", "air_flow", "L/min"),
    "Oxygen flow": ("process_timeseries", "O2_flow", "L/min"),
    "Carbon dioxide flow": ("process_timeseries", "CO2_flow", "L/min"),
    "Feed rate": ("process_timeseries", "feed_rate", "mL/(L·h)"),
    "Sensor glucose": ("process_timeseries", "sensor_glucose", "g/L"),
    "Sensor lactate": ("process_timeseries", "sensor_lactate", "g/L"),
    "Viable cell density": ("offline_assays", "viable_cell_density", "million cells/mL"),
    "Viability": ("offline_assays", "viability", "%"),
    "Offline glucose": ("offline_assays", "glucose", "g/L"),
    "Offline lactate": ("offline_assays", "lactate", "g/L"),
    "Ammonia": ("offline_assays", "ammonia", "mmol/L"),
    "Product titer": ("offline_assays", "product_titer", "g/L"),
}


def filter_measurements(frame, batches, start, end):
    return frame.loc[frame.batch_id.isin(batches) & frame.time_hr.between(start, end)].sort_values(
        ["batch_id", "time_hr"]).copy()


def summarize(tables, batches, start, end):
    """One row per selected batch, preserving batches with no window observations."""
    metadata = tables["batch_metadata"].set_index("batch_id")
    result = metadata.reindex(batches)[["media_type", "bioreactor_scale"]].copy()
    process = filter_measurements(tables["process_timeseries"], batches, start, end)
    assays = filter_measurements(tables["offline_assays"], batches, start, end)
    for title, frame, column, operation in [
        ("Peak VCD (million cells/mL)", assays, "viable_cell_density", "max"),
        ("Max offline lactate (g/L)", assays, "lactate", "max"),
        ("Mean DO (% air saturation)", process, "DO", "mean"),
        ("Min sensor glucose (g/L)", process, "sensor_glucose", "min"),
        ("pH SD (sample)", process, "pH", "std"),
    ]:
        grouped = frame.groupby("batch_id")[column]
        result[title] = grouped.agg(operation)
        result[f"{title} — n"] = grouped.count().reindex(batches, fill_value=0)
    result["Process rows in window"] = process.groupby("batch_id").size().reindex(batches, fill_value=0)
    result["Assay rows in window"] = assays.groupby("batch_id").size().reindex(batches, fill_value=0)
    quality = tables["final_quality"].set_index("batch_id")
    result["Final titer (g/L; full run)"] = quality.final_titer
    return result.reset_index()


def trend_figure(frame, variable, batches, expected_interval, colors):
    """Break lines at missing observations and gaps larger than the expected cadence."""
    _, column, unit = VARIABLES[variable]
    figure = go.Figure()
    for batch in batches:
        group = frame.loc[frame.batch_id == batch].sort_values("time_hr")
        x, y = [], []
        previous = None
        for hour, value in group[["time_hr", column]].itertuples(index=False, name=None):
            if previous is not None and hour - previous > expected_interval:
                x.append(None)
                y.append(None)
            x.append(float(hour))
            y.append(None if pd.isna(value) else float(value))
            previous = hour
        figure.add_trace(go.Scatter(x=x, y=y, name=batch, mode="lines+markers", connectgaps=False,
                                   line=dict(color=colors[batch]), marker=dict(size=4),
                                   hovertemplate=f"%{{x}} h<br>%{{y:.4g}} {unit}<extra>{batch}</extra>"))
    figure.update_layout(title=variable, xaxis_title="Elapsed time (h)", yaxis_title=f"{variable} ({unit})",
                         legend_title="Batch", hovermode="closest", height=350)
    return figure


def batch_colors(batches):
    return {batch: qualitative.Plotly[index % len(qualitative.Plotly)] for index, batch in enumerate(batches)}
