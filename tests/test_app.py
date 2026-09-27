"""Regression checks for navigation and the reviewed-cleaning workflow."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def click(self, label):
        next(button for button in self.app.button if button.label == label).click().run()
        self.assertFalse(self.app.exception, self.app.exception)

    def test_demo_cleaning_navigation_and_source_replacement(self):
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
        self.assertFalse(self.app.exception)
        self.click('Load demo data')
        self.assertEqual(len(self.app.dataframe), 4)
        self.assertEqual(len(self.app.get('download_button')), 4)
        self.app.radio[0].set_value('messy').run()
        self.assertEqual(self.app.session_state['demo_variant'], 'clean')
        self.click('Load demo data')
        self.app.switch_page('views/integration.py').run()
        self.click('Use loaded demo')
        self.click('Apply reviewed changes')
        self.assertTrue(any('blocked' in error.value for error in self.app.error))
        self.app.checkbox[0].check().run()
        self.app.checkbox[1].check().run()
        self.assertTrue(self.app.warning)
        self.click('Apply reviewed changes')
        self.assertFalse(self.app.error)
        self.assertTrue(any('60' in message.value for message in self.app.success))
        self.assertEqual(len(self.app.session_state['integration_applied']['log']), 2)
        self.assertEqual(len(self.app.session_state['integration_original']['process_timeseries']), 5098)
        for page in ['explorer', 'statistics', 'copilot', 'overview', 'integration']:
            self.app.switch_page(f'views/{page}.py').run()
            self.assertFalse(self.app.exception)
        self.assertIn('integration_applied', self.app.session_state)
        self.click('Use loaded demo')
        self.assertNotIn('integration_applied', self.app.session_state)
        self.app.radio[0].set_value('Upload files').run()
        self.assertFalse(self.app.exception)
        self.assertTrue(next(b for b in self.app.button if b.label == 'Load uploaded files').disabled)


if __name__ == '__main__':
    unittest.main()
