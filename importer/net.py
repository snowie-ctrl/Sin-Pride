"""
Every download the importer makes, through one session, so the tests can refuse them all. A failure with no answer,
a 5xx or a 429 is tried three times with a growing pause; any other refusal (a 404) is final at once.
"""
import time

import requests

RETRIES = 3
_session = requests.Session()
_session.headers["User-Agent"] = "Pride catalog importer (a personal project)"


class FetchError(Exception):
    pass


def fetchBytes(url, timeout=60):
    last = None
    for attempt in range(RETRIES):
        try:
            answer = _session.get(url, timeout=timeout)
        except requests.RequestException as error:
            last = type(error).__name__
        else:
            if answer.status_code == 200:
                return answer.content
            last = f"HTTP {answer.status_code}"
            if answer.status_code < 500 and answer.status_code != 429:
                break
        if attempt < RETRIES - 1:
            time.sleep(2 ** attempt)
    raise FetchError(f"{url}: {last}")
