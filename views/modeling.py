"""Predict batch quality or forecast within one batch; training is explicit."""
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from forecasting import SERIES, backtest, forecast
from integration import validate
from modeling import MODELS, TARGETS, compare_models, evaluate_test, features_at, fingerprint, training_data


def diagnostic_display(items):
    st.json(items)
    rows = items if isinstance(items, list) else [items]
    if any(row.get('reliable') is False for row in rows):
        st.warning('Bayesian sampling diagnostics are insufficient. Treat these estimates and intervals as provisional; increase sampling and reassess.')
    if any(row.get('warnings') for row in rows):
        st.warning('One or more model fits reported warnings; inspect them before interpreting scores.')


def regression_tab(tables, schedule):
    st.subheader('Predict final batch quality')
    target_label = st.selectbox('Target', list(TARGETS))
    target = TARGETS[target_label]
    cutoffs = [hour for hour in [72, 120, 168, 240] if hour < schedule['duration']]
    if not cutoffs:
        st.info('Final-quality prediction requires a configured run longer than 72 hours.')
        return
    cutoff = st.selectbox('Predict using data through hour', cutoffs, index=cutoffs.index(168) if 168 in cutoffs else len(cutoffs) - 1)
    models = st.multiselect('Models', MODELS, default=['Ridge', 'Random forest', 'XGBoost', 'Neural network'])
    draws = st.selectbox('BART draws and tuning iterations per chain', [100, 200, 500], index=1)
    st.caption('BART is off by default. If selected, it is skipped after a 60-second total comparison budget; other results remain available. Test evaluation has its own 60-second limit. BSTS is separate. No automated tuning. Other quality endpoints have weak signal in this demo.')
    settings = dict(target=target, cutoff=cutoff, models=models, draws=draws)
    key = fingerprint(tables, settings)
    try:
        x, y, excluded = training_data(tables, target, cutoff)
    except ValueError as error:
        st.info(str(error))
        return
    st.write(f'{len(x)} eligible batches; {excluded} missing targets excluded. One row per batch.')
    st.caption('Features use only measurements at or before the cutoff. Final quality, offline product titer, IDs, dates, lots, and operators are excluded. Means use observed samples; last means last non-missing observation. Numeric missing values are imputed inside training folds; missing counts remain features. No history is fabricated.')
    with st.expander('Feature definitions and preview'):
        st.dataframe(x.head(100))
        definitions = pd.DataFrame({'feature': x.columns,
                                    'definition': ['Metadata known at inoculation' if '.' not in column else 'Through cutoff only: ' + column for column in x.columns]})
        st.download_button('Download feature definitions', definitions.to_csv(index=False), 'feature_definitions.csv', 'text/csv')
    if st.button('Run model comparison', type='primary'):
        status = st.empty()
        try:
            with st.spinner('Training on development batches; the reserved test set is not scored here.'):
                result = compare_models(tables, target, cutoff, models, draws, status.write)
            st.session_state['ml_result'] = dict(key=key, result=result)
            st.session_state.pop('ml_test', None)
        except Exception as error:
            st.error(f'Model comparison failed: {error}')
        finally:
            status.empty()
    saved = st.session_state.get('ml_result')
    if not saved:
        return
    if saved['key'] != key:
        st.warning('Data or model settings changed. Previous results are stale; rerun the comparison.')
        return
    result = saved['result']
    st.caption(f"Development batches: {len(result['train_ids'])}; reserved test batches: {len(result['test_ids'])}. Identical three-fold splits for all models. Scores below are means across folds, not independent confidence intervals.")
    st.dataframe(result['summary'], hide_index=True)
    if any(item.get('reliable') is False for item in result['diagnostics']):
        st.warning('At least one Bayesian cross-validation fit failed sampling diagnostics. Its scores are provisional and should not determine model selection without further sampling.')
    if result['failures']:
        st.warning('Some models failed and are omitted from the leaderboard.')
        st.json(result['failures'])
    with st.expander('Fit diagnostics and fold metrics'):
        diagnostic_display(result['diagnostics'])
        st.dataframe(result['folds'], hide_index=True)
    predictions = result['predictions'].copy()
    predictions['residual'] = predictions.actual - predictions.predicted
    st.plotly_chart(px.scatter(predictions, x='actual', y='predicted', color='model', hover_name='batch_id',
                              title='Out-of-fold predictions'), width='stretch')
    st.plotly_chart(px.scatter(predictions, x='predicted', y='residual', color='model', title='Out-of-fold residuals'), width='stretch')
    for label, frame in [('Model scores', result['summary']), ('Fold metrics', result['folds']), ('Out-of-fold predictions', predictions)]:
        st.download_button(f'Download {label.lower()}', frame.to_csv(index=False), label.replace(' ', '_') + '.csv', 'text/csv')
    st.download_button('Download experiment settings and split', json.dumps(dict(**settings, train_ids=result['train_ids'], test_ids=result['test_ids'], seed=42), indent=2), 'model_experiment.json', 'application/json')
    selected = st.selectbox('Model to evaluate on reserved test batches', result['summary'].model.tolist())
    st.caption('Choose using development results. Repeated test-set evaluations make it part of model selection; those later scores are exploratory, not an untouched final assessment.')
    if st.button('Evaluate selected model on test set'):
        try:
            with st.spinner('Fitting development batches and evaluating the reserved test set…'):
                test = evaluate_test(tables, target, cutoff, selected, draws)
            st.session_state['ml_test'] = dict(key=key, model=selected, result=test)
        except Exception as error:
            st.error(f'Test evaluation failed: {error}')
    test_saved = st.session_state.get('ml_test')
    if test_saved and test_saved['key'] == key and test_saved['model'] == selected:
        test = test_saved['result']
        st.write(test['metrics'])
        st.dataframe(test['predictions'], hide_index=True)
        diagnostic_display(test['diagnostics'])
        if selected == 'BART':
            st.caption('lower/upper intervals are posterior predictive intervals for a new outcome. mean_lower95/mean_upper95 describe uncertainty in the expected response. Intervals depend on the model and sampling diagnostics.')
        st.download_button('Download test predictions', test['predictions'].to_csv(index=False), 'test_predictions.csv', 'text/csv')
    st.info('These models predict similar batches, not validated future campaigns or unseen media lots. Negative R² and weak performance are retained. No causal interpretation is implied.')


def forecast_tab(tables, schedule):
    st.subheader('Bayesian structural time-series forecast')
    batch = st.selectbox('Forecast batch', sorted(tables['batch_metadata'].batch_id))
    variable = st.selectbox('Forecast measurement', list(SERIES))
    cadence = schedule['assay_step'] if SERIES[variable][0] == 'offline_assays' else schedule['process_step']
    cutoff = st.number_input('Forecast origin (hours)', min_value=cadence, max_value=max(cadence, schedule['duration']), value=max(cadence, min(168, schedule['duration'])), step=cadence)
    horizon = st.selectbox('Forecast horizon (hours)', [24, 48, 72])
    draws = st.selectbox('BSTS draws and tuning iterations per chain', [100, 200, 500], index=0)
    st.caption('A separate Bayesian local level + trend + observation-noise model is fitted to this batch only. No seasonality or future covariates. Two sequential Metropolis chains; forecasts may take minutes. Sensor history needs 12 observed points; sparse offline titer needs 10. Missing grid points stay missing.')
    config = dict(variable=variable, batch=batch, cutoff=int(cutoff), horizon=horizon, cadence=cadence, draws=draws)
    key = fingerprint(tables, config)
    if st.button('Run Bayesian forecast', type='primary'):
        try:
            with st.spinner('Sampling structural model and forecasting…'):
                result = forecast(tables, **config)
            st.session_state['bsts_result'] = dict(key=key, result=result)
        except Exception as error:
            st.error(f'Forecast unavailable: {error}')
    saved = st.session_state.get('bsts_result')
    if saved and saved['key'] != key:
        st.warning('Forecast settings or data changed. Rerun to replace stale results.')
    if saved and saved['key'] == key:
        result = saved['result']
        future, history = result['forecast'], result['history']
        figure = go.Figure()
        for interval, color in [('95', 'rgba(70,110,220,0.12)'), ('80', 'rgba(70,110,220,0.25)')]:
            figure.add_trace(go.Scatter(x=future.time_hr, y=future[f'upper{interval}'], mode='lines', line=dict(width=0), showlegend=False))
            figure.add_trace(go.Scatter(x=future.time_hr, y=future[f'lower{interval}'], fill='tonexty', fillcolor=color,
                                       mode='lines', line=dict(width=0), name=f'{interval}% predictive interval'))
        figure.add_trace(go.Scatter(x=history.index, y=history.values, name='Observed history', mode='lines+markers', connectgaps=False))
        figure.add_trace(go.Scatter(x=future.time_hr, y=future['mean'], name='Forecast mean'))
        figure.add_vline(x=cutoff, line_dash='dash')
        figure.update_layout(xaxis_title='Elapsed time (h)', yaxis_title=variable)
        st.plotly_chart(figure, width='stretch')
        st.write(f"Sampling and forecast runtime: {result['seconds']:.1f} seconds")
        diagnostic_display(result['diagnostics'])
        st.caption('Intervals are model-based, not guarantees. Gaussian forecasts may exceed physical bounds; they are not silently clipped. Unexpected process shifts can invalidate extrapolation.')
        st.download_button('Download forecast', future.to_csv(index=False), 'bsts_forecast.csv', 'text/csv')
        st.download_button('Download forecast settings', json.dumps(config, indent=2), 'forecast_settings.json', 'application/json')
    if st.button('Run historical backtest'):
        status = st.empty()
        try:
            with st.spinner('Evaluating up to three historical origins…'):
                result = backtest(tables, **config, progress=status.write)
            st.session_state['bsts_backtest'] = dict(key=key, result=result)
        except Exception as error:
            st.error(f'Backtest unavailable: {error}')
        finally:
            status.empty()
    saved = st.session_state.get('bsts_backtest')
    if saved and saved['key'] == key:
        result = saved['result']
        st.dataframe(result['metrics'], hide_index=True)
        st.caption('Nonoverlapping forecast windows end by the selected origin. Training histories overlap; errors are not independent replicates. Coverage is evaluated only where actual measurements exist. These scores are separate from the batch-quality leaderboard.')
        if result['skipped']:
            st.write(result['skipped'])
        diagnostic_display(result['diagnostics'])
        st.download_button('Download backtest predictions', result['predictions'].to_csv(index=False), 'backtest_predictions.csv', 'text/csv')
        st.download_button('Download backtest metrics', result['metrics'].to_csv(index=False), 'backtest_metrics.csv', 'text/csv')
    elif saved:
        st.warning('Backtest results are stale; rerun for the current settings.')


st.title('Predictive Modeling & Forecasting')
if 'integration_applied' not in st.session_state:
    st.info('Prepare data and apply reviewed changes in Data Integration & Quality first.')
    st.stop()
applied = st.session_state['integration_applied']
schedule = applied.get('settings', dict(duration=336, process_step=4, assay_step=24))
tables, report = validate(applied['tables'], **schedule)
if (report.severity == 'error').any():
    st.error('Resolve blocking data-quality errors before modeling.')
    st.dataframe(report, hide_index=True)
    st.stop()
st.caption(f"Source: {st.session_state.get('integration_source', 'Prepared data')}. Models run only when requested.")
if not report.empty:
    st.warning('Quality warnings remain; missing and unusual observations can affect predictions.')
    with st.expander('Quality findings'):
        st.dataframe(report, hide_index=True)
regression, forecasting = st.tabs(['Final-quality prediction', 'Time-series forecasting'])
with regression:
    regression_tab(tables, schedule)
with forecasting:
    forecast_tab(tables, schedule)
