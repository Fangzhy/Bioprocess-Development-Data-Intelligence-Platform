import streamlit as st

st.title("Data Integration & Quality")
st.write("Connect batch metadata, process measurements, offline assays, and final quality results.")
st.info("Planned for Milestone 3, after the demo datasets are ready.")
st.subheader("Planned workflow")
st.markdown("""
1. Upload the four CSV or Excel datasets.
2. Validate columns, types, units, and batch identifiers.
3. Review missing values, duplicates, and unmatched records.
4. Choose cleaning actions and inspect the integration report.
""")
