"""Exploratory PCA and anomaly ranking at batch grain."""
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from exploration import summarize


def process_features(tables, duration):
    summary = summarize(tables, tables['batch_metadata'].batch_id.tolist(), 0, duration).set_index('batch_id')
    columns = [column for column in summary if column.startswith(('Peak VCD', 'Max offline lactate',
               'Mean DO', 'Min sensor glucose', 'pH SD')) and not column.endswith(' — n')]
    return summary[columns].sort_index()


def analyze(features):
    """Fit exploratory cohort models; no endpoint, identifier, or stress-label inputs."""
    frame = features.replace([np.inf, -np.inf], np.nan)
    dropped = [column for column in frame if frame[column].nunique(dropna=True) < 2]
    frame = frame.drop(columns=dropped)
    if frame.shape[1] < 2:
        raise ValueError('At least two nonconstant, observed process features are required.')
    excluded = frame.index[frame.isna().mean(axis=1) > .5].tolist()
    frame = frame.drop(index=excluded)
    if len(frame) < 5:
        raise ValueError('At least five batches with no more than 50% missing selected features are required.')
    # Recheck after excluding sparse rows, as variance may disappear.
    more_dropped = [column for column in frame if frame[column].nunique(dropna=True) < 2]
    frame = frame.drop(columns=more_dropped)
    if frame.shape[1] < 2:
        raise ValueError('Fewer than two varying features remain after excluding sparse batches.')
    imputed = SimpleImputer(strategy='median').fit_transform(frame)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(imputed)
    pca = PCA(svd_solver='full')
    scores = pca.fit_transform(scaled)
    forest = IsolationForest(n_estimators=200, random_state=42, n_jobs=1).fit(scaled)
    components = [f'PC{i+1}' for i in range(scores.shape[1])]
    ranked = pd.DataFrame(scores, index=frame.index, columns=components)
    ranked['anomaly_score'] = -forest.score_samples(scaled)
    ranked = ranked.sort_values('anomaly_score', ascending=False, kind='stable')
    ranked['review_rank'] = np.arange(1, len(ranked) + 1)
    return dict(scores=ranked.reset_index(),
                loadings=pd.DataFrame(pca.components_.T, index=frame.columns, columns=components).rename_axis('feature').reset_index(),
                variance=pd.DataFrame({'component': components, 'explained_fraction': pca.explained_variance_ratio_,
                                       'cumulative_fraction': np.cumsum(pca.explained_variance_ratio_)}),
                preprocessing=pd.DataFrame({'feature': frame.columns, 'imputed_cells': frame.isna().sum().to_numpy(),
                                             'median': np.nanmedian(frame, axis=0), 'scale_mean': scaler.mean_, 'scale_sd': scaler.scale_}),
                dropped_features=dropped + more_dropped, excluded_batches=excluded)


def investigate(features, batch, references):
    references = [item for item in dict.fromkeys(references) if item != batch and item in features.index]
    if len(references) < 3:
        raise ValueError('At least three other reference batches are required.')
    reference = features.loc[references]
    mean, sd = reference.mean(), reference.std(ddof=1)
    selected = features.loc[batch]
    deviation = (selected - mean) / sd.where(sd > 1e-12)
    deviation = deviation.where(reference.count() >= 3)
    result = pd.DataFrame({'selected_value': selected, 'reference_mean': mean, 'reference_sd': sd,
                           'reference_n': reference.count(), 'difference': selected - mean,
                           'standardized_deviation': deviation})
    result = result.reindex(result.standardized_deviation.abs().sort_values(ascending=False, na_position='last').index)
    return result.rename_axis('feature').reset_index()
