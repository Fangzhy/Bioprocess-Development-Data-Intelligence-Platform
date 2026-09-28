import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from data_generation import generate_clean
from multivariate import analyze, investigate, process_features
from copilot import build_evidence


class MultivariateTests(unittest.TestCase):
    def test_reproducibility_endpoint_exclusion_and_pca(self):
        tables = generate_clean()
        features = process_features(tables, 336)
        before = features.copy()
        result = analyze(features)
        pd.testing.assert_frame_equal(result['scores'], analyze(features)['scores'])
        pd.testing.assert_frame_equal(features, before)
        self.assertEqual(len(result['scores']), 60)
        self.assertAlmostEqual(result['variance'].explained_fraction.sum(), 1)
        weights = result['loadings'].drop(columns='feature').to_numpy()
        np.testing.assert_allclose(weights.T @ weights, np.eye(weights.shape[1]), atol=1e-10)
        tables['final_quality']['final_titer'] = 999
        pd.testing.assert_frame_equal(features, process_features(tables, 336))

    def test_missing_constant_and_small(self):
        features = pd.DataFrame({'a': range(8), 'b': [1, 3, 2, 5, 6, 4, 8, 9], 'constant': 1., 'empty': np.nan},
                                index=pd.Index([str(i) for i in range(8)], name='batch_id'))
        features.loc['0', ['a', 'b']] = np.nan
        features.loc['1', 'a'] = np.nan
        result = analyze(features)
        self.assertEqual(set(result['dropped_features']), {'constant', 'empty'})
        self.assertEqual(result['excluded_batches'], ['0'])
        self.assertEqual(result['preprocessing'].imputed_cells.sum(), 1)
        with self.assertRaises(ValueError):
            analyze(features.iloc[:3])
        with self.assertRaises(ValueError):
            analyze(features[['constant', 'empty']])

    def test_reference_excludes_selected_and_zero_variance(self):
        features = pd.DataFrame({'x': [10., 1, 2, 3], 'constant': [5., 2, 2, 2]}, index=['A', 'B', 'C', 'D'])
        result = investigate(features, 'A', ['A', 'B', 'C', 'D']).set_index('feature')
        self.assertEqual(result.loc['x', 'reference_n'], 3)
        self.assertEqual(result.loc['x', 'standardized_deviation'], 8)
        self.assertTrue(pd.isna(result.loc['constant', 'standardized_deviation']))
        with self.assertRaises(ValueError):
            investigate(features, 'A', ['A', 'B', 'C'])

    def test_ui_and_copilot_provenance(self):
        tables = generate_clean()
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
        app.switch_page('views/multivariate.py').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        app.session_state['integration_applied'] = {'tables': tables}
        app.run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn('anomaly_investigation', app.session_state)
        entry = app.session_state['anomaly_investigation']
        from integration import validate
        prepared, _ = validate(tables)
        evidence = build_evidence(prepared, dict(duration=336), 'Demo: clean', 'Explain an anomaly',
                                  saved={'anomaly_investigation': entry})
        self.assertTrue(any(item['topic'] == 'PCA and batch anomaly investigation' for item in evidence))
        app.multiselect[0].set_value(app.multiselect[0].value[:2]).run()
        self.assertFalse(app.exception)
        self.assertNotIn('anomaly_investigation', app.session_state)
        self.assertTrue(any('stale' in message.value for message in app.info))


if __name__ == '__main__':
    unittest.main()
