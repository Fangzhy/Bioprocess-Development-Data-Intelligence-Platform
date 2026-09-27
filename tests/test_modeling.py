import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from data_generation import generate_clean
from modeling import (features_at, split_batches, training_data, fit_predict, compare_models,
                      evaluate_test, fingerprint, preprocessor, bounded_bart)
from forecasting import history_at, forecast, backtest


class ModelingTests(unittest.TestCase):
    def test_bart_timeout_retains_other_models(self):
        with patch('modeling.bounded_bart', side_effect=TimeoutError('BART skipped: time budget')):
            result = compare_models(self.tables, 'final_titer', 168, ['BART', 'Ridge'])
        self.assertEqual(set(result['summary'].model), {'Mean baseline', 'Ridge'})
        self.assertEqual(result['failures'][0]['model'], 'BART')
        self.assertNotIn('BART', set(result['predictions'].model))

    def test_real_worker_timeout(self):
        with self.assertRaises(TimeoutError):
            bounded_bart(np.ones((3, 1)), np.arange(3.), np.ones((1, 1)), 20, timeout=.001)

    @classmethod
    def setUpClass(cls):
        cls.tables = generate_clean()

    def test_feature_cutoff_target_exclusion_and_split(self):
        before = features_at(self.tables, 168)
        changed = {name: frame.copy() for name, frame in self.tables.items()}
        for name in ('process_timeseries', 'offline_assays'):
            mask = changed[name].time_hr > 168
            for column in changed[name].select_dtypes('number'):
                if column != 'time_hr':
                    changed[name].loc[mask, column] = 999
        changed['final_quality']['final_titer'] = 999
        pd.testing.assert_frame_equal(before, features_at(changed, 168))
        self.assertFalse(any('product_titer' in column or 'final' in column for column in before))
        x, y, _ = training_data(self.tables, 'final_titer', 168)
        train, test = split_batches(x)
        self.assertEqual(len(test), 12)
        self.assertFalse(set(train) & set(test))
        small = {name: frame.iloc[:5] for name, frame in self.tables.items()}
        with self.assertRaises(ValueError):
            training_data(small, 'final_titer', 168)

    def test_preprocessing_fitted_to_train_and_unknown_media(self):
        x, _, _ = training_data(self.tables, 'final_titer', 168)
        train = x.iloc[:20].copy()
        train.loc[train.index[0], 'media_type'] = np.nan
        prep = preprocessor(train)
        prep.fit(train)
        original = prep.named_transformers_['numeric'].named_steps['impute'].statistics_.copy()
        new = x.iloc[-2:].copy()
        new['media_type'] = 'NEW'
        new['seed_density'] = 1e9
        prep.transform(new)
        np.testing.assert_array_equal(original, prep.named_transformers_['numeric'].named_steps['impute'].statistics_)

    def test_conventional_models_and_test_set(self):
        result = compare_models(self.tables, 'final_titer', 168, ['Ridge', 'Random forest', 'XGBoost', 'Neural network'])
        self.assertEqual(len(result['summary']), 5)
        self.assertFalse(result['failures'])
        self.assertFalse(set(result['predictions'].batch_id) & set(result['test_ids']))
        self.assertTrue(np.isfinite(result['summary'].RMSE).all())
        test = evaluate_test(self.tables, 'final_titer', 168, 'Ridge')
        self.assertEqual(len(test['predictions']), 12)

    def test_missing_targets_excluded_and_result_fingerprint(self):
        changed = {name: frame.copy() for name, frame in self.tables.items()}
        changed['final_quality'].loc[0, 'final_titer'] = np.nan
        self.assertEqual(training_data(changed, 'final_titer', 168)[2], 1)
        self.assertNotEqual(fingerprint(changed, {}), fingerprint(self.tables, {}))
        self.assertNotEqual(fingerprint(self.tables, {'cutoff': 72}), fingerprint(self.tables, {'cutoff': 168}))

    def test_history_grid_no_future_or_other_batch_leakage(self):
        variable = 'Sensor glucose (g/L)'
        history = history_at(self.tables, variable, 'B001', 168, 4)
        altered = {name: frame.copy() for name, frame in self.tables.items()}
        frame = altered['process_timeseries']
        frame.loc[(frame.batch_id != 'B001') | (frame.time_hr > 168), 'sensor_glucose'] = 1e6
        pd.testing.assert_series_equal(history, history_at(altered, variable, 'B001', 168, 4))
        altered['process_timeseries'] = frame.loc[~((frame.batch_id == 'B001') & (frame.time_hr == 40))]
        missing = history_at(altered, variable, 'B001', 168, 4)
        self.assertEqual(len(missing), 43)
        self.assertTrue(pd.isna(missing.loc[40]))
        with self.assertRaises(ValueError):
            history_at(self.tables, 'Offline product titer (g/L)', 'B001', 168, 24)

    def test_forecast_and_chronological_backtest(self):
        histories = []
        def fake(history, steps, draws):
            histories.append(history.copy())
            center = np.repeat(history[~np.isnan(history)][-1], steps)
            return dict(mean=center, lower80=center-1, upper80=center+1,
                        lower95=center-2, upper95=center+2, diagnostics={'reliable': False})
        result = forecast(self.tables, 'Sensor glucose (g/L)', 'B001', 168, 24, 4, predictor=fake)
        self.assertEqual(result['forecast'].time_hr.tolist(), [172, 176, 180, 184, 188, 192])
        back = backtest(self.tables, 'Sensor glucose (g/L)', 'B001', 168, 24, 4, predictor=fake)
        self.assertTrue((back['predictions'].time_hr > back['predictions'].origin_hr).all())
        self.assertLessEqual(back['predictions'].time_hr.max(), 168)
        self.assertEqual(back['predictions'].time_hr.nunique(), len(back['predictions']))
        self.assertEqual(set(back['metrics'].model), {'BSTS', 'persistence', 'linear_drift'})

    def test_ui_training_is_explicit_and_stale_results_hidden(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()
        app.switch_page('views/modeling.py').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        app.session_state['integration_applied'] = {'tables': self.tables}
        with patch('modeling.fit_predict', side_effect=AssertionError('Automatic training')):
            app.run()
        self.assertFalse(app.exception)
        app.multiselect[0].set_value(['Ridge']).run()
        next(button for button in app.button if button.label == 'Run model comparison').click().run()
        self.assertFalse(app.exception)
        self.assertIn('ml_result', app.session_state)
        app.selectbox[1].set_value(120).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('stale' in message.value for message in app.warning))


if __name__ == '__main__':
    unittest.main()
