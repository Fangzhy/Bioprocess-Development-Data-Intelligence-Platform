"""Explicit, slower compatibility smoke test: python bayesian_smoke.py."""
import time
import numpy as np
from bayesian_models import bart_predict, structural_predict


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', help='Benchmark a real demo split and sensor series using 100 draws.')
    parser.add_argument('--edge', action='store_true', help='Check missing sensor values and sparse offline titer with tiny fits.')
    args = parser.parse_args()
    if args.edge:
        from data_generation import generate_clean, make_messy
        from integration import clean_tables
        from forecasting import forecast
        tables, _ = clean_tables(make_messy(generate_clean())[0], True, True)
        for variable, batch, cutoff, cadence in [('Sensor glucose (g/L)', 'B018', 120, 4),
                                                 ('Offline product titer (g/L)', 'B001', 240, 24)]:
            result = forecast(tables, variable, batch, cutoff, 24, cadence, draws=20)
            assert len(result['forecast']) == 24 // cadence
            assert np.isfinite(result['forecast']['mean']).all()
            print('EDGE PASS', variable, result['diagnostics'], flush=True)
        raise SystemExit(0)
    if args.demo:
        from data_generation import generate_clean
        from modeling import evaluate_test
        from forecasting import forecast
        tables = generate_clean()
        start = time.monotonic()
        result = evaluate_test(tables, 'final_titer', 168, 'BART', draws=100)
        assert len(result['predictions']) == 12
        print('DEMO BART', result['metrics'], result['diagnostics'], 'seconds', time.monotonic() - start, flush=True)
        start = time.monotonic()
        result = forecast(tables, 'Sensor glucose (g/L)', 'B001', 168, 24, 4, draws=100)
        assert len(result['forecast']) == 6
        assert np.isfinite(result['forecast']['mean']).all()
        print('DEMO BSTS', result['diagnostics'], 'seconds', time.monotonic() - start, flush=True)
        raise SystemExit(0)
    x = np.arange(24, dtype=float).reshape(-1, 1) / 24
    for name, run in [
        ('BART', lambda: bart_predict(x, x[:, 0] ** 2, x[:3], draws=20)),
        ('BSTS', lambda: structural_predict(3 + np.arange(20) * .03 + np.sin(np.arange(20)) * .1, 3, draws=20)),
    ]:
        start = time.monotonic()
        result = run()
        assert result['mean'].shape == (3,), result['mean'].shape
        assert np.isfinite(result['mean']).all()
        assert np.all(result['lower95'] <= result['lower80'])
        assert np.all(result['lower80'] <= result['upper80'])
        assert np.all(result['upper80'] <= result['upper95'])
        print(name, 'PASS', round(time.monotonic() - start, 2), 'seconds', result['diagnostics'], flush=True)
