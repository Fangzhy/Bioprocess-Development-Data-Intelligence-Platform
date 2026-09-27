import streamlit as st

import pandas as pd
from data_generation import DATASETS, DEMO_DIR

st.title("Bioprocess Development Data Intelligence")
st.write("A workspace for integrating bioreactor data, comparing experimental batches, and explaining analytical findings.")
st.info("Milestone 5: explore process trends, batch-level correlations, and media-group statistics.")
st.subheader("From measurements to understanding")
st.write("Load data → Check quality → Explore batches → Analyze results → Explain findings")

left, right = st.columns(2)
with left:
    st.subheader("Bring your data together")
    st.write("Connect batch metadata, process sensor readings, offline assays, and final quality results using batch identifiers.")
    st.page_link("views/integration.py", label="Data Integration & Quality", icon=":material/dataset:")
    st.page_link("views/explorer.py", label="Process Explorer", icon=":material/monitoring:")
with right:
    st.subheader("Understand the results")
    st.write("Explore trends and statistical relationships, then request an AI explanation grounded in calculated results.")
    st.page_link("views/statistics.py", label="Statistical Analysis", icon=":material/analytics:")
    st.page_link("views/copilot.py", label="Scientific AI Copilot", icon=":material/chat:")

st.divider()
st.subheader("Explore synthetic demo data")
st.caption("Illustrative CHO simulations, not experimental measurements or a validated biological model.")
variant = st.radio("Demo variant", ["clean", "messy"], format_func=str.title, horizontal=True)
st.write("The messy variant contains deliberate data-quality defects. Both variants include unusual process batches.")
if st.button("Load demo data", type="primary"):
    try:
        tables = {name: pd.read_csv(DEMO_DIR / variant / f"{name}.csv") for name in DATASETS}
    except (OSError, ValueError) as error:
        st.error(f"Could not load bundled demo files: {error}")
    else:
        st.session_state["demo_data"] = tables
        st.session_state["demo_variant"] = variant

if "demo_data" in st.session_state:
    loaded = st.session_state["demo_variant"]
    tables = st.session_state["demo_data"]
    st.success(f"Loaded {loaded} synthetic data for {len(tables['batch_metadata'])} batches in this session.")
    if variant != loaded:
        st.info(f"Click Load demo data to replace the currently loaded {loaded} tables with {variant} data.")
    for tab, name in zip(st.tabs([name.replace('_', ' ').title() for name in DATASETS]), DATASETS):
        with tab:
            frame = tables[name]
            st.caption(f"{len(frame):,} rows · {len(frame.columns)} columns · first 100 rows shown")
            st.dataframe(frame.head(100), hide_index=True, width="stretch")
            st.download_button("Download CSV", frame.to_csv(index=False).encode("utf-8"),
                               file_name=f"{loaded}_{name}.csv", mime="text/csv", key=f"download_{name}")
else:
    st.write("Choose a variant and load it to preview and download the four datasets.")

with st.expander("Data dictionary and simulation assumptions"):
    st.markdown((DEMO_DIR.parents[1] / "docs" / "data_dictionary.md").read_text(encoding="utf-8"))
