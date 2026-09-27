"""Within-batch forecasts and chronological backtests, with no future predictors."""
import time
import numpy as np
import pandas as pd

from modeling import scores

SERIES = {'Sensor glucose (g/L)': ('process_timeseries', 'sensor_glucose'),
          'Sensor lactate (g/L)': ('process_timeseries', 'sensor_lactate'),
          'Dissolved oxygen (%)': ('process_timeseries', 'DO'),
          'Offline product titer (g/L)': ('offline_assays', 'product_titer')}


def history_at(tables, variable, batch, cutoff, cadence):
    name, column = SERIES[variable]
    if cutoff % cadence:
        raise ValueError('The cutoff must align with the sampling interval.')
    source = tables[name].loc[(tables[name].batch_id == batch) & (tables[name].time_hr <= cutoff)]
    if source.time_hr.duplicated().any():
        raise ValueError('Duplicate time points must be resolved first.')
    if (source.time_hr % cadence != 0).any():
        raise ValueError('Off-grid times found; use a compatible expected sampling interval.')
    grid = source.set_index('time_hr')[column].reindex(range(0, cutoff + 1, cadence))
    if len(grid) > 200:
        raise ValueError('This interactive forecast supports at most 200 historical grid points.')
    minimum = 10 if name == 'offline_assays' else 12
    if grid.notna().sum() < minimum:
        raise ValueError(f'At least {minimum} observed historical points are required; choose a later cutoff.')
    if grid.notna().mean() < .6:
        raise ValueError('At least 60% of the historical grid must be observed.')
    if grid.dropna().nunique() < 2:
        raise ValueError('Constant history is not suitable for this structural model.')
    return grid


def forecast(tables, variable, batch, cutoff, horizon, cadence, draws=200, predictor=None):
    from bayesian_models import structural_predict
    if horizon <= 0 or horizon % cadence:
        raise ValueError('Forecast horizon must be a positive multiple of the sampling interval.')
    history = history_at(tables, variable, batch, cutoff, cadence)
    start = time.monotonic()
    result = (predictor or structural_predict)(history.to_numpy(dtype=float), horizon // cadence, draws=draws)
    future = pd.DataFrame({key: result[key] for key in ('mean', 'lower80', 'upper80', 'lower95', 'upper95')})
    future.insert(0, 'time_hr', np.arange(cutoff + cadence, cutoff + horizon + 1, cadence))
    observed = history.dropna()
    future['persistence'] = observed.iloc[-1]
    slope = (observed.iloc[-1] - observed.iloc[0]) / (observed.index[-1] - observed.index[0])
    future['linear_drift'] = observed.iloc[-1] + slope * (future.time_hr - observed.index[-1])
    return dict(forecast=future, history=history, diagnostics=result['diagnostics'], seconds=time.monotonic() - start)


def backtest(tables, variable, batch, cutoff, horizon, cadence, draws=200, predictor=None, progress=None):
    """Up to three nonoverlapping past origins, all ending by current cutoff."""
    name, column = SERIES[variable]
    truth = tables[name].loc[tables[name].batch_id == batch].set_index('time_hr')[column]
    predictions, skipped, diagnostics = [], [], []
    for origin in sorted({cutoff - horizon * k for k in (1, 2, 3) if cutoff - horizon * k >= 0}):
        try:
            if progress:
                progress(f'Backtest origin {origin} h')
            result = forecast(tables, variable, batch, origin, horizon, cadence, draws, predictor)
            frame = result['forecast'].copy()
            frame['actual'] = truth.reindex(frame.time_hr).to_numpy()
            frame['origin_hr'] = origin
            frame['horizon_hr'] = frame.time_hr - origin
            predictions.append(frame)
            diagnostics.append(dict(origin_hr=origin, **result['diagnostics']))
        except ValueError as error:
            skipped.append(f'{origin} h: {error}')
    if not predictions:
        raise ValueError('No eligible backtest origins. Increase history or shorten the horizon. ' + '; '.join(skipped))
    joined = pd.concat(predictions, ignore_index=True)
    rows = []
    for horizon_value, subset in [('All', joined)] + list(joined.groupby('horizon_hr')):
        observed = subset.dropna(subset=['actual'])
        if observed.empty:
            continue
        for name in ('mean', 'persistence', 'linear_drift'):
            rows.append(dict(horizon_hr=horizon_value, model='BSTS' if name == 'mean' else name,
                             n=len(observed), origins=observed.origin_hr.nunique(),
                             coverage80=float(observed.actual.between(observed.lower80, observed.upper80).mean()) if name == 'mean' else np.nan,
                             coverage95=float(observed.actual.between(observed.lower95, observed.upper95).mean()) if name == 'mean' else np.nan,
                             width95=float((observed.upper95 - observed.lower95).mean()) if name == 'mean' else np.nan,
                             **scores(observed.actual, observed[name])))
    return dict(predictions=joined, metrics=pd.DataFrame(rows), skipped=skipped, diagnostics=diagnostics)
