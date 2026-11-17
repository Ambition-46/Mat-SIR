"""Bounded provider retries with metadata-only diagnostics (never credentials)."""
import random
import re
import threading
import time

import requests


class ModelServiceError(RuntimeError):
    pass


_inflight = threading.BoundedSemaphore(2)


def post_json(url, headers, payload, *, timeout=90, attempts=4, events=None, stage='model'):
    for attempt in range(max(1, min(int(attempts), 6))):
        start = time.perf_counter()
        event = {'stage': stage, 'attempt': attempt + 1}
        retry = False
        data = None
        try:
            with _inflight:
                response = requests.post(url, headers=headers, json=payload, timeout=(10, timeout))
            event['http_status'] = response.status_code
            retry = response.status_code in (408, 429, 500, 502, 503, 504)
            if response.ok:
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError('Invalid response object')
                event['success'] = True
                if isinstance(data.get('model'), str):
                    event['model'] = data['model'][:100]
                if isinstance(data.get('choices'), list) and data['choices']:
                    event['finish_reason'] = data['choices'][0].get('finish_reason')
            else:
                event['success'] = False
                try:
                    code = response.json().get('error', {}).get('code')
                    if isinstance(code, str) and re.fullmatch(r'[\w.-]{1,100}', code):
                        event['error_code'] = code
                except (ValueError, AttributeError):
                    pass
        except (requests.Timeout, requests.ConnectionError) as exc:
            event.update(success=False, error_type=type(exc).__name__)
            retry = True
        except (ValueError, requests.RequestException) as exc:
            event.update(success=False, error_type=type(exc).__name__)
        event['seconds'] = time.perf_counter() - start
        if events is not None:
            events.append(event)
        if event['success']:
            return data
        if not retry or attempt + 1 >= max(1, min(int(attempts), 6)):
            raise ModelServiceError('Model request failed: ' + str(event.get('http_status', event.get('error_type'))))
        time.sleep(min(12, 2 ** attempt) + random.uniform(0, .25))
