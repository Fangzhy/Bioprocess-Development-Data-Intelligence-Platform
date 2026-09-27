"""Upload, inspect, review cleaning, and integrate session-scoped data."""
import streamlit as st

from data_generation import DATASETS
from integration import BATCH_QUERY, clean_tables, integrate_sql, read_upload, validate

st.title("Data Integration & Quality")
st.write("Inspect four related datasets, review cleaning choices, and build a batch-level SQL table.")
source = st.radio("Data source", ["Loaded demo", "Upload files"], horizontal=True)
if source == "Loaded demo":
    if "demo_data" not in st.session_state:
        st.info("Load a demo on Overview first.")
    if st.button("Use loaded demo", disabled="demo_data" not in st.session_state):
        st.session_state["integration_original"] = {
            name: frame.copy(deep=True) for name, frame in st.session_state["demo_data"].items()
        }
        st.session_state["integration_source"] = f"Demo: {st.session_state['demo_variant']}"
        st.session_state.pop("integration_applied", None)
else:
    st.caption("One CSV or .xlsx file per dataset; Excel uses the first worksheet. Maximum 10 MB and 100,000 rows per file. Column names and units must match the data dictionary.")
    uploads = {name: st.file_uploader(name.replace("_", " ").title(), type=["csv", "xlsx"], key=f"upload_{name}") for name in DATASETS}
    units = st.checkbox("I confirm that measurement units match the data dictionary.")
    if st.button("Load uploaded files", disabled=not (all(item is not None for item in uploads.values()) and units)):
        try:
            incoming = {name: read_upload(item.getvalue(), item.name) for name, item in uploads.items()}
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state["integration_original"] = incoming
            st.session_state["integration_source"] = "Uploaded files"
            st.session_state.pop("integration_applied", None)

if "integration_original" not in st.session_state:
    st.stop()

st.caption(f"Active working source: {st.session_state['integration_source']}. Loading another source replaces this workspace; selecting a source alone does not.")
with st.expander("Expected sampling schedule", expanded=False):
    st.caption("Defaults match the demo. Set these for your experiment; missing time points are warnings, not interpolated.")
    duration = st.number_input("Run duration (hours)", min_value=1, max_value=10000, value=336, step=1)
    process_step = st.number_input("Process interval (hours)", min_value=1, max_value=10000, value=4, step=1)
    assay_step = st.number_input("Assay interval (hours)", min_value=1, max_value=10000, value=24, step=1)
settings = dict(duration=int(duration), process_step=int(process_step), assay_step=int(assay_step))
original = st.session_state["integration_original"]
prepared, initial_report = validate(original, **settings)

st.subheader("Source quality report")
st.caption("Counts describe findings and may overlap. Example row numbers include the header row. Range checks are broad plausibility checks, not validated process limits.")
st.dataframe(initial_report, hide_index=True)
st.download_button("Download source report", initial_report.to_csv(index=False), "source_quality_report.csv", "text/csv")
with st.expander("Original source tables"):
    for name, frame in original.items():
        st.write(name)
        st.dataframe(frame.head(100), hide_index=True)

st.subheader("Review cleaning")
deduplicate = st.checkbox("Remove exact duplicate rows")
exclude = st.checkbox("Exclude rows with unknown batch IDs")
candidate, change_log = clean_tables(prepared, deduplicate, exclude)
_, remaining = validate(candidate, **settings)
st.write(f"Proposed removals: {len(change_log)} rows. Missing values and unusual measurements are retained.")
st.dataframe(change_log, hide_index=True)
with st.expander("Quality findings after proposed changes"):
    st.dataframe(remaining, hide_index=True)
if st.button("Apply reviewed changes"):
    st.session_state["integration_applied"] = {
        "tables": candidate, "log": change_log,
        "options": (deduplicate, exclude), "settings": settings,
    }

if "integration_applied" not in st.session_state:
    st.info("Review the proposal and apply it to prepare working copies. You can apply with no removals selected.")
    st.stop()

applied = st.session_state["integration_applied"]
if applied["options"] != (deduplicate, exclude):
    st.warning("Cleaning choices have changed. Downloads and SQL below still use the last applied choices.")
working = applied["tables"]
_, final_report = validate(working, **settings)
st.subheader("Prepared data and remaining findings")
st.dataframe(final_report, hide_index=True)
st.download_button("Download remaining report", final_report.to_csv(index=False), "remaining_quality_report.csv", "text/csv")
st.download_button("Download cleaning log", applied["log"].to_csv(index=False), "cleaning_log.csv", "text/csv")
for name, frame in working.items():
    st.download_button(f"Download prepared {name}", frame.to_csv(index=False), f"prepared_{name}.csv", "text/csv", key=f"prepared_{name}")

st.subheader("Batch-level SQL integration")
st.caption("Extra input columns remain in prepared downloads; SQL uses the documented schema. Measurement gaps can remain as warnings. The database is private to this operation and is closed afterward.")
st.code(BATCH_QUERY, language="sql")
if (final_report.severity == "error").any():
    st.error("SQL integration is blocked. Resolve errors in the source files or apply the available cleaning actions.")
else:
    batch = integrate_sql(working, **settings)
    st.success(f"Integrated {len(batch)} metadata batches without multiplying rows.")
    st.dataframe(batch, hide_index=True)
    st.download_button("Download integrated batches", batch.to_csv(index=False), "integrated_batches.csv", "text/csv")
