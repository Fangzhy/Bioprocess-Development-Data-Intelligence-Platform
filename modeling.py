"""Leakage-safe batch features and comparable regression experiments."""
import hashlib
import json
import time
import warnings
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

TARGETS = {'Final titer (g/L)': 'final_titer', 'Aggregation (%)': 'aggregation',
           'Purity (%)': 'purity', 'Downstream yield (%)': 'yield',
           'Glycosylation metric (%)': 'glycosylation_metric'}
MODELS = ['Mean baseline', 'Ridge', 'Random forest', 'XGBoost', 'Neural network', 'BART']
SEED = 42
BART_SECONDS = 60


def bounded_bart(x, y, future, draws, timeout=BART_SECONDS):
    """Run BART separately; terminate its own process tree on timeout."""
    if timeout <= 0:
        raise TimeoutError('BART skipped: its 60-second time budget was exhausted.')
    with tempfile.TemporaryDirectory(prefix='bioprocess_bart_') as folder:
        source = Path(folder) / 'input.npz'
        destination = Path(folder) / 'result.json'
        np.savez(source, x=x, y=y, future=future, draws=draws)
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('bart_worker.py')),
                                    str(source), str(destination)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                   start_new_session=os.name != 'nt')
        try:
            _, error = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False)
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            process.communicate()
            raise TimeoutError('BART skipped: exceeded its 60-second time budget. Other model results are retained.') from None
        if process.returncode:
            raise RuntimeError(f'BART worker failed: {error[-2000:]}')
        result = json.loads(destination.read_text(encoding='utf-8'))
        return {key: value if key == 'diagnostics' else np.asarray(value) for key, value in result.items()}


def fingerprint(tables, settings):
    digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode())
    for name in sorted(tables):
        digest.update(name.encode())
        digest.update(tables[name].to_csv(index=False).encode())
    return digest.hexdigest()


def features_at(tables, cutoff):
    """One row per batch, with no final-quality or post-cutoff input features."""
    result = tables['batch_metadata'].set_index('batch_id')[['media_type', 'bioreactor_scale', 'seed_density']].copy()
    result['media_type'] = result.media_type.astype(object).where(result.media_type.notna(), np.nan)
    for name, columns in {
        'process_timeseries': ['pH', 'DO', 'feed_rate', 'sensor_glucose', 'sensor_lactate'],
        'offline_assays': ['viable_cell_density', 'viability', 'glucose', 'lactate', 'ammonia'],
    }.items():
        history = tables[name].loc[tables[name].time_hr <= cutoff].sort_values(['batch_id', 'time_hr'])
        for column in columns:
            grouped = history.groupby('batch_id')[column]
            for aggregation in ('mean', 'min', 'max', 'last', 'count'):
                result[f'{name}.{column}.{aggregation}'] = grouped.agg(aggregation)
            result[f'{name}.{column}.count'] = result[f'{name}.{column}.count'].fillna(0)
    return result.sort_index()


def training_data(tables, target, cutoff):
    x = features_at(tables, cutoff)
    y = tables['final_quality'].set_index('batch_id')[target].reindex(x.index)
    available = y.notna() & np.isfinite(y)
    if available.sum() < 30:
        raise ValueError('At least 30 batches with observed targets are required (60 recommended).')
    if available.sum() > 500:
        raise ValueError('This interactive prototype supports at most 500 labeled batches per experiment.')
    if y[available].nunique() < 2:
        raise ValueError('The selected target is constant.')
    return x.loc[available], y.loc[available], int((~available).sum())


def split_batches(x):
    train, test = train_test_split(np.arange(len(x)), test_size=.2, random_state=SEED)
    return np.sort(train), np.sort(test)


def preprocessor(x):
    numeric = [column for column in x if column != 'media_type']
    return ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True)),
                              ('scale', StandardScaler())]), numeric),
        ('media', Pipeline([('impute', SimpleImputer(strategy='constant', fill_value='Unknown', keep_empty_features=True)),
                            ('encode', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), ['media_type']),
    ])


def scores(actual, predicted):
    return dict(RMSE=float(np.sqrt(mean_squared_error(actual, predicted))),
                MAE=float(mean_absolute_error(actual, predicted)),
                R2=float(r2_score(actual, predicted)) if len(actual) > 1 and np.var(actual) > 0 else np.nan)


def fit_predict(name, x_train, y_train, x_predict, draws=200, bart_timeout=BART_SECONDS):
    start = time.monotonic()
    prep = preprocessor(x_train)
    train = prep.fit_transform(x_train)
    predict = prep.transform(x_predict)
    if name == 'BART':
        result = bounded_bart(train, np.asarray(y_train, dtype=float), predict, draws, bart_timeout)
    else:
        if name == 'Mean baseline':
            model = DummyRegressor()
        elif name == 'Ridge':
            model = Ridge(alpha=10)
        elif name == 'Random forest':
            model = RandomForestRegressor(n_estimators=150, max_depth=4, min_samples_leaf=3, n_jobs=1, random_state=SEED)
        elif name == 'XGBoost':
            from xgboost import XGBRegressor
            model = XGBRegressor(n_estimators=100, max_depth=2, learning_rate=.04, reg_lambda=5,
                                 min_child_weight=3, n_jobs=1, random_state=SEED)
        elif name == 'Neural network':
            model = TransformedTargetRegressor(
                regressor=MLPRegressor(hidden_layer_sizes=(12, 6), activation='tanh', alpha=1,
                                       solver='lbfgs', max_iter=600, random_state=SEED),
                transformer=StandardScaler())
        else:
            raise ValueError('Unknown model.')
        with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
            model.fit(train, y_train)
            predicted = model.predict(predict)
        result = dict(mean=predicted, diagnostics={'warnings': [str(item.message) for item in caught]})
    result['seconds'] = time.monotonic() - start
    return result


def compare_models(tables, target, cutoff, models, draws=200, progress=None):
    x, y, excluded = training_data(tables, target, cutoff)
    train, test = split_batches(x)
    folds = list(KFold(3, shuffle=True, random_state=SEED).split(train))
    records, predictions, failures, diagnostics = [], [], [], []
    for name in dict.fromkeys(['Mean baseline'] + list(models)):
        model_started = time.monotonic()
        local_records, local_predictions = [], []
        try:
            for fold, (a, b) in enumerate(folds, 1):
                if progress:
                    progress(f'{name}: cross-validation fold {fold}/3')
                fit_ids, val_ids = train[a], train[b]
                remaining = BART_SECONDS - (time.monotonic() - model_started)
                result = fit_predict(name, x.iloc[fit_ids], y.iloc[fit_ids], x.iloc[val_ids], draws,
                                     bart_timeout=remaining if name == 'BART' else BART_SECONDS)
                local_records.append(dict(model=name, fold=fold, seconds=result['seconds'], **scores(y.iloc[val_ids], result['mean'])))
                diagnostics.append(dict(model=name, fold=fold, **result['diagnostics']))
                for position, actual, predicted in zip(val_ids, y.iloc[val_ids], result['mean']):
                    local_predictions.append(dict(model=name, fold=fold, batch_id=x.index[position], actual=actual, predicted=predicted))
            records.extend(local_records)
            predictions.extend(local_predictions)
        except Exception as error:
            failures.append(dict(model=name, error=f'{type(error).__name__}: {error}'))
    details = pd.DataFrame(records)
    if details.empty:
        raise ValueError(f'No model completed: {failures}')
    summary = details.groupby('model').agg(RMSE=('RMSE', 'mean'), RMSE_fold_SD=('RMSE', 'std'),
                                          MAE=('MAE', 'mean'), R2=('R2', 'mean'), seconds=('seconds', 'sum')).reset_index()
    baseline = summary.loc[summary.model == 'Mean baseline', 'RMSE'].iloc[0]
    summary['RMSE improvement vs mean (%)'] = 100 * (baseline - summary.RMSE) / baseline if baseline else np.nan
    return dict(summary=summary.sort_values('RMSE'), folds=details, predictions=pd.DataFrame(predictions),
                failures=failures, diagnostics=diagnostics, excluded=excluded,
                train_ids=x.index[train].tolist(), test_ids=x.index[test].tolist())


def evaluate_test(tables, target, cutoff, model, draws=200):
    x, y, _ = training_data(tables, target, cutoff)
    train, test = split_batches(x)
    result = fit_predict(model, x.iloc[train], y.iloc[train], x.iloc[test], draws)
    prediction = pd.DataFrame(dict(batch_id=x.index[test], actual=y.iloc[test].to_numpy(), predicted=result['mean']))
    prediction['residual'] = prediction.actual - prediction.predicted
    for key in ('lower80', 'upper80', 'lower95', 'upper95', 'mean_lower95', 'mean_upper95'):
        if key in result:
            prediction[key] = result[key]
    return dict(metrics=scores(prediction.actual, prediction.predicted), predictions=prediction,
                diagnostics=result['diagnostics'], seconds=result['seconds'])
