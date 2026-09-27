import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
from streamlit.testing.v1 import AppTest

from copilot import (CopilotError, DEFAULT_MODEL, SYSTEM_PROMPT, build_evidence, explanation_key,
                     fallback_summary, generate_explanation, load_config, clean_json)
from data_generation import generate_clean
from integration import validate


class CopilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = generate_clean()
        cls.schedule = dict(duration=336, process_step=4, assay_step=24)
        cls.evidence = build_evidence(cls.tables, cls.schedule, 'Demo: clean', 'Explain statistical results')

    def client(self, status=200, content='Evidence [E1] describes a synthetic study.'):
        session = Mock()
        session.get.return_value = Mock(status_code=200)
        session.get.return_value.json.return_value = {'data': [{'id': DEFAULT_MODEL, 'pricing': {'prompt': '0', 'completion': '0'}}]}
        response = Mock(status_code=status)
        response.json.return_value = {'model': DEFAULT_MODEL, 'usage': {'cost': 0},
                                      'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}
        session.post.return_value = response
        return session

    def test_configuration_precedence_alias_and_root_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('OPEN_ROUTER_API=file-secret\nOPENROUTER_MODEL=test:free\n')
            self.assertEqual(load_config(environ={}, env_path=path), ('file-secret', 'test:free'))
            self.assertEqual(load_config({'OPEN_ROUTER_API': 'secret-store'}, {'OPENROUTER_API_KEY': 'environment'}, path)[0], 'secret-store')

    def test_success_free_only_and_no_key_in_body(self):
        client = self.client()
        result = generate_explanation(self.evidence, 'private-key', DEFAULT_MODEL, client)
        self.assertEqual(result['cost'], 0)
        body = client.post.call_args.kwargs['json']
        self.assertNotIn('private-key', json.dumps(body))
        self.assertEqual(body['provider']['max_price']['completion'], 0)
        self.assertFalse(body['reasoning']['enabled'])
        self.assertIn('never invent', SYSTEM_PROMPT)
        self.assertIn('provisional', SYSTEM_PROMPT)
        self.assertIn('not instructions', SYSTEM_PROMPT)

    def test_missing_key_paid_model_changed_pricing(self):
        client = self.client()
        for key, model in [('', DEFAULT_MODEL), ('key', 'paid/model')]:
            with self.assertRaises(CopilotError):
                generate_explanation(self.evidence, key, model, client)
        client.get.return_value.json.return_value['data'][0]['pricing']['prompt'] = '0.1'
        with self.assertRaises(CopilotError):
            generate_explanation(self.evidence, 'key', DEFAULT_MODEL, client)
        client.post.assert_not_called()

    def test_errors_retry_and_truncated_response(self):
        client = self.client(status=429)
        sleep = Mock()
        with self.assertRaises(CopilotError):
            generate_explanation(self.evidence, 'key', DEFAULT_MODEL, client, sleep)
        self.assertEqual(client.post.call_count, 2)
        sleep.assert_called_once_with(2)
        client = self.client()
        client.post.return_value.json.return_value['choices'][0]['finish_reason'] = 'length'
        with self.assertRaises(CopilotError):
            generate_explanation(self.evidence, 'key', DEFAULT_MODEL, client)
        client.post.side_effect = requests.Timeout('private-key')
        with self.assertRaises(CopilotError) as caught:
            generate_explanation(self.evidence, 'private-key', DEFAULT_MODEL, client)
        self.assertNotIn('private-key', str(caught.exception))

    def test_stale_evidence_missing_models_and_cache_key(self):
        self.assertEqual(clean_json({'p': 1e-18})['p'], 1e-18)
        evidence = build_evidence(self.tables, self.schedule, 'Demo: clean', 'Compare predictive models',
                                  saved={'ml_result': {'data_signature': 'obsolete'}})
        self.assertTrue(any(item['topic'] == 'Unavailable analysis' for item in evidence))
        self.assertIn('no LLM used', fallback_summary(evidence))
        self.assertNotEqual(explanation_key(evidence, DEFAULT_MODEL), explanation_key(self.evidence, DEFAULT_MODEL))

    def test_ui_explicit_generation_reuse_and_fallback(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
        app.session_state['integration_applied'] = {'tables': self.tables, 'settings': self.schedule}
        app.session_state['integration_source'] = 'Demo: clean'
        with patch('copilot.load_config', return_value=('test-key', DEFAULT_MODEL)), patch('copilot.generate_explanation', return_value={'text': 'Synthetic results [E1].', 'model': DEFAULT_MODEL, 'cost': 0}) as generate:
            app.switch_page('views/copilot.py').run()
            self.assertFalse(app.exception)
            generate.assert_not_called()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            app.button[0].click().run()
            self.assertEqual(generate.call_count, 1)
            app.selectbox[0].set_value('Compare predictive models').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('hidden' in item.value for item in app.info))
        with patch('copilot.load_config', return_value=('', DEFAULT_MODEL)):
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.button[0].disabled)


if __name__ == '__main__':
    unittest.main()
