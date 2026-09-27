"""Explore validated, explicitly applied working data."""
import streamlit as st
import plotly.graph_objects as go

from exploration import VARIABLES, batch_colors, filter_measurements, summarize, trend_figure
from integration import validate

st.title("Process Explorer")
st.write("Compare process trajectories and descriptive batch summaries.")
if "integration_applied" not in st.session_state:
    st.info("First load data in Data Integration & Quality, review the cleaning choices, and click Apply reviewed changes.")
    st.page_link("views/integration.py", label="Prepare data")
    st.stop()

applied = st.session_state["integration_applied"]
settings = applied.get("settings", dict(duration=336, process_step=4, assay_step=24))
tables, report = validate(applied["tables"], **settings)
st.caption(f"Source: {st.session_state.get('integration_source', 'Prepared data')}. Uses the last applied working copy and sampling schedule.")
if (report.severity == "error").any():
    st.error("Resolve blocking quality errors and apply the corrected data before exploring.")
    st.dataframe(report, hide_index=True)
    st.stop()
if not report.empty:
    st.warning("Quality warnings remain. Missing values and time gaps are retained; summaries use available observations.")
    with st.expander("Remaining quality findings"):
        st.dataframe(report, hide_index=True)

metadata = tables["batch_metadata"]
media_options = sorted(metadata.media_type.dropna().unique().tolist())
media = st.multiselect("Media types (empty means all)", media_options)
eligible = metadata if not media else metadata.loc[metadata.media_type.isin(media)]
batch_options = sorted(eligible.batch_id.tolist())
batches = st.multiselect("Batches (up to 8)", batch_options, default=batch_options[:3], max_selections=8)
variables = st.multiselect("Measurements (up to 6)", list(VARIABLES),
                           default=["pH", "Dissolved oxygen", "Viable cell density", "Product titer"],
                           max_selections=6)
start, end = st.slider("Time window (hours)", 0, settings["duration"], (0, settings["duration"]))
if not batches:
    st.info("Select at least one batch to explore.")
    st.stop()

filtered = {name: filter_measurements(tables[name], batches, start, end)
            for name in ("process_timeseries", "offline_assays")}
colors = batch_colors(batches)
st.caption("Separate axes retain measurement units. Sensor and offline measurements stay distinct. Lines break at missing values and intervals longer than the configured sampling cadence; no interpolation is performed.")
st.subheader("Process trends")
if not variables:
    st.info("Select measurements to display trends. Batch summaries remain available below.")
for variable in variables:
    name, column, unit = VARIABLES[variable]
    frame = filtered[name]
    if frame.empty or frame[column].notna().sum() == 0:
        st.info(f"No observed values for {variable} in this time window.")
        continue
    step = settings["process_step"] if name == "process_timeseries" else settings["assay_step"]
    figure = trend_figure(frame, variable, batches, step, colors)
    st.plotly_chart(figure, width="stretch", key=f"trend_{column}")

st.subheader("Batch comparison")
st.caption("Window metrics use only the selected hours. Means are observation-weighted, missing values are excluded, and n counts non-missing measurements. Sample SD requires at least two values. Final titer is the full-run quality endpoint, independent of the time window.")
summary = summarize(tables, batches, start, end)
st.dataframe(summary, hide_index=True)
metric_options = [column for column in summary if column not in
                  ("batch_id", "media_type", "bioreactor_scale") and not column.endswith(" — n")
                  and not column.endswith("rows in window")]
metric = st.selectbox("Compare metric", metric_options)
observed = summary.loc[summary[metric].notna()]
if observed.empty:
    st.info("No observed values for this comparison metric.")
else:
    figure = go.Figure(go.Bar(x=observed.batch_id.tolist(), y=observed[metric].tolist(),
                              marker_color=[colors[batch] for batch in observed.batch_id]))
    figure.update_layout(xaxis_title="Batch", yaxis_title=metric, title=metric)
    st.plotly_chart(figure, width="stretch", key="batch_comparison")
st.download_button("Download batch summary", summary.to_csv(index=False), "batch_summary.csv", "text/csv")
with st.expander("Filtered observations and downloads"):
    for name, frame in filtered.items():
        st.write(f"{name}: {len(frame):,} rows; first 100 shown")
        st.dataframe(frame.head(100), hide_index=True)
        st.download_button(f"Download filtered {name}", frame.to_csv(index=False),
                           f"filtered_{name}.csv", "text/csv")
