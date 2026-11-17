import unittest
from unittest.mock import Mock, patch
import requests
from .model_transport import post_json, ModelServiceError


class TransportTests(unittest.TestCase):
    @patch('apps.intent_engine.model_transport.time.sleep')
    def test_retry_transient_and_record_metadata(self, sleep):
        events = []
        busy = Mock(status_code=429, ok=False)
        good = Mock(status_code=200, ok=True)
        good.json.return_value = {'choices': []}
        with patch('apps.intent_engine.model_transport.requests.post', side_effect=[busy, requests.Timeout('sensitive'), good]) as request:
            self.assertEqual(post_json('http://example', {'Authorization':'secret'}, {}, events=events), {'choices':[]})
        self.assertEqual(request.call_count, 3)
        self.assertEqual([e['success'] for e in events], [False,False,True])
        self.assertNotIn('secret', str(events))
        self.assertNotIn('sensitive', str(events))

    def test_permanent_errors_do_not_retry(self):
        for status in (400,401,403,404):
            with self.subTest(status=status), patch('apps.intent_engine.model_transport.requests.post', return_value=Mock(status_code=status,ok=False)) as request:
                with self.assertRaises(ModelServiceError):post_json('http://example', {}, {})
                self.assertEqual(request.call_count,1)

    @patch('apps.intent_engine.model_transport.time.sleep')
    def test_attempts_are_bounded(self, sleep):
        with patch('apps.intent_engine.model_transport.requests.post', side_effect=requests.Timeout) as request:
            with self.assertRaises(ModelServiceError):post_json('http://example', {}, {}, attempts=3)
            self.assertEqual(request.call_count,3)


if __name__ == '__main__':unittest.main()
