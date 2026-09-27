"""Evidence-grounded explanations; no API call until an explicit button click."""
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from copilot import (CopilotError, build_evidence, evidence_text, explanation_key,
                     fallback_summary, generate_explanation, load_config)
from integration import validate

st.title("Scientific AI Copilot")
st.write("Explain computed results, compare models, and summarize a study.")
try:
    secrets = st.secrets.to_dict()
except (StreamlitSecretNotFoundError, FileNotFoundError):
    secrets = {}
api_key, model = load_config(secrets=secrets)
st.caption(f"Configured model: {model}. Free-only requests; no paid fallback.")
if not api_key:
    st.info("No API key found. Template summaries still work. Configure OPEN_ROUTER_API or OPENROUTER_API_KEY in the root .env or Streamlit secrets.")

if "integration_applied" not in st.session_state:
    st.info("Prepare and apply data in Data Integration & Quality first.")
    st.page_link("views/integration.py", label="Prepare data")
    st.stop()
applied = st.session_state["integration_applied"]
schedule = applied.get("settings", dict(duration=336, process_step=4, assay_step=24))
tables, quality = validate(applied["tables"], **schedule)
if (quality.severity == "error").any():
    st.error("Resolve blocking data-quality errors before requesting explanations.")
    st.dataframe(quality, hide_index=True)
    st.stop()

task = st.selectbox("Explanation task", ["Explain statistical results", "Compare predictive models",
                                        "Explain a forecast", "Generate study summary"])
st.caption("Statistical explanations compute full-run final-titer/media comparisons and peak-VCD correlation for this cohort. Modeling explanations use the latest completed results matching these data, with their recorded settings.")
saved = {name: st.session_state.get(name) for name in ("ml_result", "bsts_result")}
evidence = build_evidence(tables, schedule, st.session_state.get("integration_source", "Uploaded files"),
                          task, saved, quality)
payload = evidence_text(evidence)
key = explanation_key(evidence, model)
st.subheader("Evidence preview")
st.write("Only the summary below and explanation instructions will be sent to OpenRouter and its model provider. Raw input tables and your API key are not part of this preview.")
st.json(evidence, expanded=False)
with st.expander("Explanation instructions"):
    from copilot import SYSTEM_PROMPT
    st.code(SYSTEM_PROMPT)
if '"reliable": false' in payload:
    st.warning("Bayesian sampling diagnostics failed. Those results and intervals are provisional regardless of the AI explanation.")
if any(item["topic"] == "Unavailable analysis" for item in evidence):
    st.info("Some requested results are unavailable or stale. Run that analysis on the current data first; the copilot cannot infer missing results.")
st.download_button("Download evidence", payload, "copilot_evidence.json", "application/json")

cache = st.session_state.setdefault("copilot_cache", {})
if st.button("Generate AI explanation", type="primary", disabled=not api_key):
    if key not in cache:
        try:
            with st.spinner("Requesting a free-model explanation…"):
                cache[key] = generate_explanation(evidence, api_key, model)
            # Bound per-session response storage without sharing uploaded-data results.
            while len(cache) > 10:
                del cache[next(iter(cache))]
        except CopilotError as error:
            st.error(str(error))
            st.info("The computed template summary below remains available.")
    else:
        st.info("Reused the explanation for this exact evidence and model; no request was sent.")

if key in cache:
    answer = cache[key]
    st.subheader("AI-generated explanation")
    st.caption(f"Returned model: {answer['model']} · Reported request cost: {answer.get('cost')}")
    st.warning("AI explanations may contain unsupported claims. Check each claim against the evidence; this is not independent scientific validation.")
    st.text(answer["text"])
    st.download_button("Download explanation", answer["text"] + "\n\nEvidence:\n" + payload,
                       "scientific_explanation.txt", "text/plain")
elif cache:
    st.info("Previous explanations do not match the current evidence/settings and are hidden. Generate a new explanation.")

with st.expander("Computed template summary (always available)", expanded=not bool(api_key)):
    template = fallback_summary(evidence)
    st.text(template)
    st.download_button("Download template summary", template, "computed_study_summary.txt", "text/plain")
