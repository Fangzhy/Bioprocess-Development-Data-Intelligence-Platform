import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from data_generation import generate_clean, make_messy
from exploration import batch_colors, filter_measurements, summarize, trend_figure
from integration import clean_tables


class ExplorationTests(unittest.TestCase):
    def test_window_summary_counts_and_no_mutation(self):
        tables = generate_clean()
        before = tables['process_timeseries'].copy(deep=True)
        tables['process_timeseries'].loc[0, 'DO'] = float('nan')
        result = summarize(tables, ['B001', 'B002'], 0, 24).set_index('batch_id')
        self.assertEqual(result.loc['B001', 'Process rows in window'], 7)
        self.assertEqual(result.loc['B001', 'Assay rows in window'], 2)
        self.assertEqual(result.loc['B001', 'Mean DO (% air saturation) — n'], 6)
        expected = before.loc[(before.batch_id == 'B001') & before.time_hr.between(4, 24), 'DO'].mean()
        self.assertAlmostEqual(result.loc['B001', 'Mean DO (% air saturation)'], expected)
        self.assertEqual(result.loc['B001', 'Final titer (g/L; full run)'], tables['final_quality'].iloc[0].final_titer)
        self.assertEqual(len(tables['process_timeseries']), 5100)
        empty = summarize(tables, ['B001'], 1, 3).iloc[0]
        self.assertEqual(empty['Process rows in window'], 0)
        self.assertTrue(pd.isna(empty['Peak VCD (million cells/mL)']))
        single = summarize(tables, ['B001'], 0, 0).iloc[0]
        self.assertTrue(pd.isna(single['pH SD (sample)']))

    def test_chart_sorts_breaks_gaps_and_keeps_missing(self):
        frame = pd.DataFrame({'batch_id': ['B001'] * 4, 'time_hr': [16, 0, 4, 8], 'DO': [40, 45, None, 42]})
        before = frame.copy(deep=True)
        chart = trend_figure(frame, 'Dissolved oxygen', ['B001'], 4, batch_colors(['B001']))
        self.assertEqual(list(chart.data[0].x), [0, 4, 8, None, 16])
        self.assertEqual(list(chart.data[0].y), [45, None, 42, None, 40])
        self.assertFalse(chart.data[0].connectgaps)
        pd.testing.assert_frame_equal(frame, before)
        filtered = filter_measurements(frame, ['B001'], 4, 8)
        self.assertEqual(filtered.time_hr.tolist(), [4, 8])

    def test_explorer_empty_blocked_and_interactive_states(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
        app.switch_page('views/explorer.py').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        messy, _ = make_messy(generate_clean())
        app.session_state['integration_applied'] = {'tables': messy, 'settings': dict(duration=336, process_step=4, assay_step=24)}
        app.run()
        self.assertTrue(app.error)
        clean, _ = clean_tables(messy, True, True)
        app.session_state['integration_applied'] = {'tables': clean, 'settings': dict(duration=336, process_step=4, assay_step=24)}
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get('plotly_chart')), 5)
        self.assertTrue(app.warning)
        app.multiselect[0].set_value(['Media-2']).run()
        self.assertFalse(app.exception)
        selected = app.multiselect[1].value
        ids = clean['batch_metadata'].query("media_type == 'Media-2'").batch_id.tolist()
        self.assertTrue(set(selected).issubset(ids))
        app.slider[0].set_value((1, 3)).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        app.multiselect[2].set_value([]).run()
        self.assertFalse(app.exception)
        app.multiselect[1].set_value([]).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get('plotly_chart')), 0)


if __name__ == '__main__':
    unittest.main()
