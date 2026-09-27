"""Lazy Bayesian dependencies and bounded CPU sampling configurations."""
import os

# A pure-Python PyTensor linker supports Windows without a compiler.
# Set before PyTensor imports. Users may override this for a compiled deployment.
os.environ.setdefault('PYTENSOR_FLAGS', 'cxx=,mode=FAST_COMPILE')
import numpy as np


def diagnostics(idata, variables):
    import arviz as az
    try:
        report = az.summary(idata, var_names=variables, kind='diagnostics')
        rhat = float(report.r_hat.max())
        ess = float(report.ess_bulk.min())
        return dict(max_rhat=rhat, min_ess_bulk=ess,
                    reliable=bool(np.isfinite(rhat) and rhat <= 1.05 and ess >= 100))
    except Exception as error:
        return dict(reliable=False, diagnostic_error=str(error))


def intervals(samples):
    return dict(mean=np.mean(samples, axis=0), lower80=np.quantile(samples, .1, axis=0),
                upper80=np.quantile(samples, .9, axis=0), lower95=np.quantile(samples, .025, axis=0),
                upper95=np.quantile(samples, .975, axis=0))


def bart_predict(x, y, future, draws=200):
    import pymc as pm
    import pymc_bart as pmb
    center, scale = float(y.mean()), max(float(y.std()), 1e-6)
    scaled = (y - center) / scale
    with pm.Model() as model:
        data = pm.Data('features', x)
        mu = pmb.BART('mu', data, scaled, m=20)
        sigma = pm.HalfNormal('sigma', 1)
        pm.Normal('outcome', mu=mu, sigma=sigma, observed=scaled, shape=mu.shape)
        idata = pm.sample(draws=draws, tune=draws, chains=2, cores=1, random_seed=42,
                          progressbar=False, compute_convergence_checks=False, blas_cores=1)
        pm.set_data({'features': future})
        posterior = pm.sample_posterior_predictive(idata, var_names=['mu', 'outcome'],
                                                  sample_vars=['mu', 'outcome'], random_seed=43, progressbar=False)
    group = posterior.posterior_predictive
    assert group['mu'].shape[-1] == len(future), 'BART did not predict new feature rows'
    latent = np.asarray(group['mu']).reshape(-1, len(future)) * scale + center
    observed = np.asarray(group['outcome']).reshape(-1, len(future)) * scale + center
    result = intervals(observed)
    result['mean'] = latent.mean(axis=0)
    result['mean_lower95'] = np.quantile(latent, .025, axis=0)
    result['mean_upper95'] = np.quantile(latent, .975, axis=0)
    result['diagnostics'] = diagnostics(idata, ['sigma', 'mu'])
    if 'diverging' in idata.sample_stats:
        divergent = int(np.asarray(idata.sample_stats['diverging']).sum())
        result['diagnostics']['divergences'] = divergent
        result['diagnostics']['reliable'] &= divergent == 0
    result['diagnostics']['draws_per_chain'] = draws
    return result


def structural_predict(history, steps, draws=200):
    import pandas as pd
    import pymc as pm
    from pymc_extras.statespace import structural as structural
    center, scale = float(np.nanmean(history)), max(float(np.nanstd(history)), 1e-6)
    data = pd.DataFrame({'data': (np.asarray(history) - center) / scale},
                        index=pd.RangeIndex(len(history), name='time'))
    model = (structural.LevelTrend(order=2, innovations_order=2) + structural.MeasurementError()).build(
        verbose=False, mode='FAST_COMPILE')
    with pm.Model(coords=model.coords):
        pm.Normal('initial_level_trend', mu=[0, 0], sigma=[2, .5], dims='state_level_trend')
        pm.HalfNormal('sigma_level_trend', sigma=[.2, .05], dims='shock_level_trend')
        pm.HalfNormal('sigma_MeasurementError', sigma=.5)
        import pytensor.tensor as pt
        pm.Deterministic('P0', pt.as_tensor_variable(np.eye(2) * 0.1))
        model.build_statespace_graph(data)
        idata = pm.sample(draws=draws, tune=draws, chains=2, cores=1, random_seed=42,
                          step=pm.Metropolis(), progressbar=False, compute_convergence_checks=False, blas_cores=1)
    prediction = model.forecast(idata, periods=steps, filter_output='filtered', random_seed=43,
                                verbose=False, progressbar=False)
    observed = np.asarray(prediction['forecast_observed'])
    observed = observed.reshape(-1, observed.shape[-2])
    if observed.shape[1] != steps:
        raise ValueError('Forecast output does not match the requested horizon.')
    observed = observed * scale + center
    result = intervals(observed)
    result['diagnostics'] = diagnostics(idata, ['initial_level_trend', 'sigma_level_trend', 'sigma_MeasurementError'])
    result['diagnostics']['draws_per_chain'] = draws
    return result
