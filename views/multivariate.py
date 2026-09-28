"""PCA, batch anomaly ranking, and descriptive investigation."""
import streamlit as st
import plotly.express as px

from integration import validate
from modeling import fingerprint
from multivariate import analyze, investigate, process_features

st.title('PCA & Anomaly Investigation')
if 'integration_applied' not in st.session_state:
    st.info('Prepare and apply data in Data Integration & Quality first.')
    st.stop()
applied = st.session_state['integration_applied']
schedule = applied.get('settings', dict(duration=336, process_step=4, assay_step=24))
tables, report = validate(applied['tables'], **schedule)
if (report.severity == 'error').any():
    st.error('Resolve blocking quality errors before multivariate analysis.')
    st.stop()
if not report.empty:
    st.warning('Quality warnings remain. Incomplete histories may bias process summaries.')
st.caption('One row per batch. Full-run process features only; quality outcomes and synthetic stress labels are not model inputs.')
features = process_features(tables, schedule['duration'])
selected_features = st.multiselect('Process features', list(features), default=list(features))
settings = dict(features=selected_features, duration=schedule['duration'])
key = fingerprint(tables, settings)
st.caption('Remove constant/all-missing features; exclude batches missing over half the selected varying features; median-impute remaining cells and standardize. Models fit the current cohort for exploration, not predictive validation.')
if st.button('Run PCA and anomaly ranking', type='primary'):
    st.session_state.pop('anomaly_investigation', None)
    try:
        result = analyze(features[selected_features])
        st.session_state['pca_result'] = dict(key=key, result=result)
    except ValueError as error:
        st.error(str(error))
saved = st.session_state.get('pca_result')
if not saved:
    st.stop()
if saved['key'] != key:
    st.session_state.pop('anomaly_investigation', None)
    st.info('Data or feature settings changed. Rerun to replace stale results.')
    st.stop()
result = saved['result']
with st.expander('Preprocessing details'):
    st.dataframe(result['preprocessing'], hide_index=True)
    st.write('Dropped features:', result['dropped_features'])
    st.write('Excluded batches:', result['excluded_batches'])
metadata = tables['batch_metadata'][['batch_id', 'media_type']]
scores = result['scores'].merge(metadata, on='batch_id', validate='one_to_one')
st.subheader('PCA scores and explained variance')
st.plotly_chart(px.scatter(scores, x='PC1', y='PC2', color='media_type', hover_name='batch_id',
                          hover_data=['review_rank', 'anomaly_score']), width='stretch')
st.dataframe(result['variance'], hide_index=True)
pc = st.selectbox('Loading component', result['variance'].component.tolist())
st.caption('Loadings shown are PCA component coefficients on standardized features, not causal effects. Component signs are arbitrary; the first two PCs may omit substantial variation.')
st.plotly_chart(px.bar(result['loadings'], x=pc, y='feature', orientation='h'), width='stretch')
st.subheader('Anomaly review ranking')
st.caption('Higher score means more unusual under Isolation Forest. Scores are not failure probabilities; review ranks do not establish defective batches or root causes. Detection uses all retained standardized features, not just PC1/PC2.')
st.dataframe(scores, hide_index=True)
batch = st.selectbox('Investigate batch', scores.batch_id.tolist())
mode = st.radio('Reference group', ['Same media, other analyzed batches', 'All other analyzed batches'], horizontal=True)
references = scores.loc[scores.batch_id != batch]
if mode.startswith('Same media'):
    media = scores.loc[scores.batch_id == batch, 'media_type'].iloc[0]
    references = references.loc[references.media_type == media]
st.caption(f'Reference: {len(references)} other analyzed batches. This group can contain unusual runs and is not a validated successful-batch baseline.')
try:
    differences = investigate(features[result['preprocessing'].feature.tolist()], batch, references.batch_id.tolist())
except ValueError as error:
    st.session_state.pop('anomaly_investigation', None)
    st.info(str(error))
else:
    st.dataframe(differences, hide_index=True)
    st.caption('Deviations use original, observed batch summaries, not imputed values. Blank standardized deviations indicate missing values, fewer than three observed references, or zero reference variance. These are descriptive deviations, not feature attributions for Isolation Forest.')
    observed = differences.dropna(subset=['standardized_deviation'])
    if not observed.empty:
        st.plotly_chart(px.bar(observed, x='standardized_deviation', y='feature', orientation='h'), width='stretch')
    quality = tables['final_quality'].loc[tables['final_quality'].batch_id == batch]
    st.write('Final quality (interpretation only; excluded from detection)')
    st.dataframe(quality, hide_index=True)
    st.session_state['anomaly_investigation'] = dict(data_signature=fingerprint(tables, {}), settings=settings,
        result=dict(batch=batch, reference_mode=mode, reference_count=len(references),
                    ranking=scores.loc[scores.batch_id == batch, ['review_rank', 'anomaly_score']],
                    variance=result['variance'], deviations=differences,
                    limitations='Exploratory cohort ranking, not a probability or causal/root-cause finding. Reference runs are not known successful controls.'))
    st.download_button('Download batch deviations', differences.to_csv(index=False), 'batch_deviations.csv', 'text/csv')
    st.page_link('views/copilot.py', label='Explain this investigation with the copilot')
for name in ('scores', 'loadings', 'variance', 'preprocessing'):
    st.download_button(f'Download {name}', result[name].to_csv(index=False), f'pca_{name}.csv', 'text/csv')
