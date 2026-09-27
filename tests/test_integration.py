from io import BytesIO
import unittest

import pandas as pd

from data_generation import generate_clean, make_messy
from integration import clean_tables, integrate_sql, read_upload, validate


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.clean = generate_clean()

    def test_clean_sql_preserves_batches(self):
        _, report = validate(self.clean)
        self.assertTrue(report.empty, report.to_string())
        batch = integrate_sql(self.clean)
        self.assertEqual(len(batch), 60)
        self.assertFalse(batch.batch_id.duplicated().any())
        self.assertEqual(batch.final_titer.tolist(), self.clean['final_quality'].final_titer.tolist())

    def test_messy_findings_cleaning_and_immutability(self):
        messy, _ = make_messy(self.clean)
        prepared, report = validate(messy)
        counts = report.groupby('issue')['count'].sum().to_dict()
        self.assertEqual(counts['missing_value'], 3)
        self.assertEqual(counts['exact_duplicate'], 1)
        self.assertEqual(counts['unknown_batch'], 1)
        self.assertEqual(counts['missing_timepoints'], 4)
        with self.assertRaises(ValueError):
            integrate_sql(prepared)
        working, log = clean_tables(prepared, True, True)
        self.assertEqual(len(log), 2)
        self.assertEqual(len(working['process_timeseries']), 5097)
        self.assertEqual(len(working['offline_assays']), 899)
        self.assertEqual(len(integrate_sql(working)), 60)
        original, _ = make_messy(self.clean)
        for name in messy:
            pd.testing.assert_frame_equal(messy[name], original[name])

    def test_bad_schema_types_keys_and_date_block(self):
        self.clean['process_timeseries'] = self.clean['process_timeseries'].drop(columns='DO')
        self.clean['offline_assays']['glucose'] = self.clean['offline_assays']['glucose'].astype(object)
        self.clean['offline_assays'].loc[0, 'glucose'] = 'not a number'
        self.clean['batch_metadata'].loc[0, 'experiment_date'] = 'not a date'
        conflict = self.clean['final_quality'].iloc[[0]].copy()
        conflict['final_titer'] = 99
        self.clean['final_quality'] = pd.concat([self.clean['final_quality'], conflict], ignore_index=True)
        _, report = validate(self.clean)
        self.assertTrue({'missing_columns', 'invalid_numeric', 'invalid_date', 'conflicting_key'} <= set(report.issue))
        working, _ = clean_tables(self.clean, True, True)
        with self.assertRaises(ValueError):
            integrate_sql(working)

    def test_missing_keys_nonfinite_and_range(self):
        self.clean['batch_metadata'].loc[0, 'batch_id'] = None
        self.clean['offline_assays'].loc[0, 'time_hr'] = -1
        self.clean['process_timeseries'].loc[0, 'DO'] = float('inf')
        _, report = validate(self.clean)
        self.assertTrue({'missing_value', 'out_of_range', 'invalid_numeric'} <= set(report.issue))
        with self.assertRaises(ValueError):
            integrate_sql(self.clean)

    def test_left_join_keeps_batch_without_quality(self):
        self.clean['final_quality'] = self.clean['final_quality'].iloc[1:]
        batch = integrate_sql(self.clean)
        self.assertEqual(len(batch), 60)
        self.assertTrue(pd.isna(batch.loc[0, 'final_titer']))

    def test_csv_excel_and_bad_upload(self):
        frame = pd.DataFrame({'batch_id': ['001', 'NA'], 'value': ['1', '']})
        csv = read_upload(frame.to_csv(index=False).encode(), 'test.csv')
        self.assertEqual(csv.batch_id.tolist(), ['001', 'NA'])
        output = BytesIO()
        frame.to_excel(output, index=False, engine='openpyxl')
        excel = read_upload(output.getvalue(), 'test.xlsx')
        pd.testing.assert_frame_equal(csv, excel)
        for data, name in [(b'', 'empty.csv'), (b'bad', 'bad.xlsx'), (b'bad', 'bad.txt')]:
            with self.assertRaises(ValueError):
                read_upload(data, name)


if __name__ == '__main__':
    unittest.main()
