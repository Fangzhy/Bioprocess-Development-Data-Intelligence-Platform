"""Statistical exploration using one row per independent batch."""
import streamlit as st
import plotly.express as px
import pandas as pd

from integration import validate
from statistical_analysis import batch_features, compare_groups, correlation_result

st.title("Statistical Analysis")
st.write("Explore batch-level associations and compare media groups.")
if "integration_applied" not in st.session_state:
    st.info("Prepare data in Data Integration & Quality and apply reviewed changes first.")
    st.page_link("views/integration.py", label="Prepare data")
    st.stop()
applied = st.session_state["integration_applied"]
settings = applied.get("settings", dict(duration=336, process_step=4, assay_step=24))
tables, report = validate(applied["tables"], **settings)
if (report.severity == "error").any():
    st.error("Resolve blocking quality errors before statistical analysis.")
    st.dataframe(report, hide_index=True)
    st.stop()
st.caption(f"Source: {st.session_state.get('integration_source', 'Prepared data')}. One row per batch; summaries use the full configured run duration.")
if not report.empty:
    st.warning("Quality warnings remain. Analyses exclude missing values, and incomplete trajectories can bias batch summaries.")
    with st.expander("Quality findings"):
        st.dataframe(report, hide_index=True)
frame = batch_features(tables, settings["duration"])
options = sorted(frame.media_type.dropna().unique().tolist())
media = st.multiselect("Media groups (empty means all)", options)
if media:
    frame = frame.loc[frame.media_type.isin(media)]
metrics = [column for column in frame if column not in ("batch_id", "media_type", "bioreactor_scale")
           and not column.endswith(" — n") and not column.endswith("rows in window")]
st.write(f"{len(frame)} batches in the selected cohort.")
st.caption("Independence is a study-design assumption and cannot be verified here. Shared lots, dates, or operators may confound associations. Synthetic demo results describe the simulation, not biological evidence.")
with st.expander("Batch features and measurement counts"):
    st.dataframe(frame, hide_index=True)
    st.download_button("Download statistical cohort", frame.to_csv(index=False), "statistical_cohort.csv", "text/csv")

st.subheader("Correlation")
x = st.selectbox("Predictor metric", metrics)
y = st.selectbox("Response metric", metrics, index=len(metrics) - 1)
correlation = correlation_result(frame, x, y)
if correlation["status"] != "ok":
    st.info(correlation["status"])
else:
    st.write(f"Pearson r = {correlation['r']:.3f}; 95% CI [{correlation['ci_low']:.3f}, {correlation['ci_high']:.3f}]")
    st.write(f"Two-sided p = {correlation['p']:.4g}; complete pairs = {correlation['n']}; excluded batches = {correlation['excluded']}")
    st.caption("Pearson measures linear association. Its p-value and Fisher confidence interval assume independent observations and an appropriate bivariate-normal model. Inspect outliers and nonlinearity; correlation does not establish causation.")
    st.plotly_chart(px.scatter(frame, x=x, y=y, color="media_type", hover_name="batch_id"), width="stretch")
    st.download_button("Download correlation result", pd.DataFrame([dict(predictor=x, response=y, **correlation)]).to_csv(index=False),
                       "correlation.csv", "text/csv")

st.subheader("Compare media groups")
outcome = st.selectbox("Group comparison metric", metrics, index=len(metrics) - 1)
method = st.radio("ANOVA method", ["Welch", "Classical"], horizontal=True)
st.caption("Welch ANOVA allows unequal group variances. Classical ANOVA assumes equal variances. Both test equality of group means; neither identifies which pairs differ.")
summary, result, diagnostics = compare_groups(frame, outcome, method)
st.dataframe(summary, hide_index=True)
st.caption("Mean intervals are separate 95% Student-t intervals, not simultaneous intervals or tests of pairwise differences. SD is the sample standard deviation.")
st.plotly_chart(px.box(frame, x="media_type", y=outcome, color="media_type", points="all", hover_name="batch_id"), width="stretch")
if result["status"] != "ok":
    st.info(result["status"])
else:
    st.write(f"{method} ANOVA: F = {result['F']:.3f}; p = {result['p']:.4g}; excluded batches = {result['excluded']}")
    st.write(f"Descriptive eta-squared = {result['eta_squared']:.3f}")
    st.caption("Eta-squared is the observed between-group share of total variation; it is not a causal effect or a Welch-adjusted effect estimate.")
    with st.expander("Assumption diagnostics", expanded=True):
        st.write(f"Median-centered Levene p = {result['levene_p']:.4g}")
        st.dataframe(diagnostics, hide_index=True)
        st.caption("Shapiro-Wilk checks within-group normality (3–5,000 observations); blank means unavailable. Small samples have low diagnostic power. Large p-values do not establish normality or equal variances. Method selection should reflect study design, not just these tests.")
        if (diagnostics.shapiro_p < .05).any():
            st.warning("At least one group shows evidence against normality. Inspect its distribution and interpret mean-based inference cautiously.")
        if method == "Classical" and result["levene_p"] < .05:
            st.warning("The equal-variance assumption is questionable. Consider the Welch result.")
st.download_button("Download group summaries", summary.to_csv(index=False), "media_group_summaries.csv", "text/csv")
st.download_button("Download ANOVA result", pd.DataFrame([dict(metric=outcome, **result)]).to_csv(index=False), "anova_result.csv", "text/csv")
st.download_button("Download diagnostics", diagnostics.to_csv(index=False), "assumption_diagnostics.csv", "text/csv")
st.info("These are exploratory, unadjusted tests. Repeatedly trying metrics or filters increases false-positive risk. Pre-specify confirmatory hypotheses and consider multiplicity; no automatic significance verdict or causal conclusion is generated.")
