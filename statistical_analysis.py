"""Batch-level descriptive and inferential statistics."""
import warnings

import numpy as np
import pandas as pd
from scipy import stats

from exploration import summarize


def batch_features(tables, duration):
    ids = tables['batch_metadata'].batch_id.tolist()
    return summarize(tables, ids, 0, duration)


def correlation_result(frame, x, y):
    if x == y:
        return {'status': 'Choose two different metrics.'}
    pairs = frame[[x, y]].replace([np.inf, -np.inf], np.nan).dropna()
    result = {'n': len(pairs), 'excluded': len(frame) - len(pairs)}
    if len(pairs) < 4:
        return dict(result, status='At least four complete batches are required for correlation and its interval.')
    if any(pairs[column].nunique() < 2 for column in (x, y)):
        return dict(result, status='Correlation is undefined for a constant metric.')
    with warnings.catch_warnings(record=True) as caught:
        outcome = stats.pearsonr(pairs[x], pairs[y])
        interval = outcome.confidence_interval()
    if caught or not np.isfinite([outcome.statistic, outcome.pvalue, interval.low, interval.high]).all():
        return dict(result, status='Numerically unstable correlation; inspect nearly constant metrics.')
    return dict(result, status='ok', r=float(outcome.statistic), p=float(outcome.pvalue),
                ci_low=float(interval.low), ci_high=float(interval.high))


def compare_groups(frame, metric, method='Welch'):
    """Complete-case media summaries, mean intervals, and omnibus group test."""
    rows, samples, diagnostics = [], [], []
    for name, group in frame.groupby('media_type', dropna=True):
        values = group[metric].replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
        n = len(values)
        mean = float(np.mean(values)) if n else np.nan
        sd = float(np.std(values, ddof=1)) if n > 1 else np.nan
        margin = float(stats.t.ppf(.975, n - 1) * sd / np.sqrt(n)) if n > 1 else np.nan
        rows.append(dict(media_type=name, n=n, missing=len(group) - n, mean=mean, sd=sd,
                         ci_low=mean - margin, ci_high=mean + margin))
        samples.append(values)
        normal_p = float(stats.shapiro(values).pvalue) if 3 <= n <= 5000 and sd > 0 else np.nan
        diagnostics.append(dict(media_type=name, shapiro_p=normal_p))
    summary = pd.DataFrame(rows, columns=['media_type', 'n', 'missing', 'mean', 'sd', 'ci_low', 'ci_high'])
    result = {'method': method, 'excluded': int(frame[metric].isna().sum() +
              (frame.media_type.isna() & frame[metric].notna()).sum())}
    if len(samples) < 2 or any(len(sample) < 3 for sample in samples):
        result['status'] = 'Select at least two media groups with three observed batches each.'
    elif any(np.var(sample) == 0 for sample in samples):
        result['status'] = 'A group has zero variance; inference is unavailable. Inspect the descriptive results.'
    else:
        with warnings.catch_warnings(record=True):
            test = stats.f_oneway(*samples, equal_var=method == 'Classical')
            levene = stats.levene(*samples, center='median')
        all_values = np.concatenate(samples)
        total = float(np.sum((all_values - all_values.mean()) ** 2))
        between = sum(len(sample) * (sample.mean() - all_values.mean()) ** 2 for sample in samples)
        result.update(status='ok', F=float(test.statistic), p=float(test.pvalue),
                      eta_squared=float(between / total), levene_p=float(levene.pvalue))
        if not np.isfinite([test.statistic, test.pvalue]).all():
            result['status'] = 'Numerically unstable comparison; inspect data ranges.'
    return summary, result, pd.DataFrame(diagnostics, columns=['media_type', 'shapiro_p'])
