"""Shared layout and navigation for the bioprocess app."""
import streamlit as st

st.set_page_config(page_title="Bioprocess Data Intelligence", page_icon=":material/science:", layout="wide")
with st.sidebar:
    st.title("Bioprocess Data Intelligence")
    st.caption("Explore process development, one batch at a time.")

page = st.navigation([
    st.Page("views/overview.py", title="Overview", icon=":material/home:", default=True),
    st.Page("views/integration.py", title="Data Integration & Quality", icon=":material/dataset:"),
    st.Page("views/explorer.py", title="Process Explorer", icon=":material/monitoring:"),
    st.Page("views/statistics.py", title="Statistical Analysis", icon=":material/analytics:"),
    st.Page("views/copilot.py", title="Scientific AI Copilot", icon=":material/chat:"),
])
page.run()
