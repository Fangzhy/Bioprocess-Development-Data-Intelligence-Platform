import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from data_generation import generate_clean
from statistical_analysis import batch_features, compare_groups, correlation_result


class StatisticsTests(unittest.TestCase):
    def test_known_classical_anova_and_effect(self):
        frame = pd.DataFrame({'media_type': ['A'] * 3 + ['B'] * 3,
                              'value': [1, 2, 3, 4, 5, 6]})
        summary, result, _ = compare_groups(frame, 'value', 'Classical')
        self.assertEqual(result['status'], 'ok')
        self.assertAlmostEqual(result['F'], 13.5)
        self.assertAlmostEqual(result['eta_squared'], 13.5 / 17.5)
        self.assertAlmostEqual(result['p'], 0.0213116411287567)
        self.assertEqual(summary.n.tolist(), [3, 3])
        self.assertEqual(summary['mean'].tolist(), [2, 5])
        _, welch, _ = compare_groups(frame, 'value')
        self.assertAlmostEqual(welch['F'], 13.5)

    def test_correlation_missing_constant_and_small(self):
        frame = pd.DataFrame({'x': [1, 2, 3, 4, np.nan], 'y': [2, 4, 6, 8, 10]})
        result = correlation_result(frame, 'x', 'y')
        self.assertEqual(result['status'], 'ok')
        self.assertAlmostEqual(result['r'], 1)
        self.assertEqual(result['n'], 4)
        self.assertEqual(result['excluded'], 1)
        self.assertNotEqual(correlation_result(frame.iloc[:2], 'x', 'y')['status'], 'ok')
        frame['x'] = 1
        self.assertNotEqual(correlation_result(frame, 'x', 'y')['status'], 'ok')
        self.assertNotEqual(correlation_result(frame, 'x', 'x')['status'], 'ok')

    def test_small_missing_and_constant_groups(self):
        frame = pd.DataFrame({'media_type': ['A'] * 3 + ['B'] * 3, 'v': [1, 2, 3, 4, 5, np.nan]})
        summary, result, _ = compare_groups(frame, 'v')
        self.assertNotEqual(result['status'], 'ok')
        self.assertEqual(summary.n.tolist(), [3, 2])
        self.assertEqual(result['excluded'], 1)
        frame['v'] = 1
        self.assertNotEqual(compare_groups(frame, 'v')[1]['status'], 'ok')

    def test_batch_grain_and_app_workflow(self):
        tables = generate_clean()
        frame = batch_features(tables, 336)
        self.assertEqual(len(frame), 60)
        self.assertTrue(frame.batch_id.is_unique)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
        app.switch_page('views/statistics.py').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        app.session_state['integration_applied'] = {'tables': tables}
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get('plotly_chart')), 2)
        app.radio[0].set_value('Classical').run()
        self.assertFalse(app.exception)
        app.multiselect[0].set_value(['Media-1']).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('at least two' in item.value for item in app.info))
        app.selectbox[1].set_value(app.selectbox[0].value).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('different' in item.value for item in app.info))


if __name__ == '__main__':
    unittest.main()
