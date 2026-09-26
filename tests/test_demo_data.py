"""Run with python -m unittest discover -s tests -v."""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from data_generation import DATASETS, DEMO_DIR, export_demo, generate_clean, make_messy


class DemoDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = generate_clean()

    def test_keys_time_grids_and_ranges(self):
        ids = set(self.clean["batch_metadata"].batch_id)
        for name, count in zip(DATASETS, (60, 5100, 900, 60)):
            frame = self.clean[name]
            self.assertEqual(len(frame), count)
            self.assertFalse(frame.isna().any().any())
            self.assertEqual(set(frame.batch_id), ids)
            keys = ["batch_id", "time_hr"] if "time_hr" in frame else ["batch_id"]
            self.assertFalse(frame.duplicated(keys).any())
            if "time_hr" in frame:
                step = 4 if name == "process_timeseries" else 24
                for _, group in frame.groupby("batch_id"):
                    self.assertEqual(group.time_hr.tolist(), list(range(0, 337, step)))
        for name, columns in {
            "process_timeseries": ["DO"], "offline_assays": ["viability"],
            "final_quality": ["purity", "aggregation", "glycosylation_metric", "yield"],
        }.items():
            for column in columns:
                self.assertTrue(self.clean[name][column].between(0, 100).all())
        last = self.clean["offline_assays"].query("time_hr == 336").set_index("batch_id").product_titer
        final = self.clean["final_quality"].set_index("batch_id").final_titer
        pd.testing.assert_series_equal(last, final, check_names=False)

    def test_seed_controls_output(self):
        again = generate_clean()
        for name in DATASETS:
            pd.testing.assert_frame_equal(self.clean[name], again[name])
        self.assertFalse(self.clean["offline_assays"].equals(generate_clean(7)["offline_assays"]))

    def test_injected_defects_and_original_unchanged(self):
        messy, manifest = make_messy(self.clean)
        self.assertEqual(len(manifest), 8)
        self.assertEqual(sum(int(df.isna().sum().sum()) for df in messy.values()), 3)
        process = messy["process_timeseries"]
        self.assertEqual(len(process), 5098)
        self.assertEqual(int(process.duplicated().sum()), 1)
        self.assertEqual(set(messy["offline_assays"].batch_id) - set(messy["batch_metadata"].batch_id), {"B999"})
        self.assertEqual(set(range(0, 337, 4)) - set(process.query("batch_id == 'B020'").time_hr), {160, 164, 168})
        fresh = generate_clean()
        for name in DATASETS:
            pd.testing.assert_frame_equal(self.clean[name], fresh[name])

    def test_bundled_csvs_match_reproducible_export(self):
        with tempfile.TemporaryDirectory() as temp:
            export_demo(temp)
            for file in Path(temp).rglob("*.csv"):
                self.assertEqual(file.read_bytes(), (DEMO_DIR / file.relative_to(temp)).read_bytes())


if __name__ == "__main__":
    unittest.main()
