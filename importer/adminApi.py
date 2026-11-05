"""
plutus's admin routes (/api/pride-admin, LAN only; docs/api.md). A failure with no answer or a 5xx is tried three
times with a pause; a refusal (a 4xx, or {"status": "error"}) is raised at once, because sending the same thing again
would be refused again. Messages name the route, never the address, so a report can be shown to anyone.
"""
import time

import requests

import config

RETRIES = 3
_http = requests.Session()


class AdminError(Exception):
    pass


def configured():
    return bool(config.ADMIN_BASE and config.ADMIN_TOKEN)


def _request(method, path, json=None, data=None, timeout=120):
    if not configured():
        raise AdminError("ADMIN_BASE and ADMIN_TOKEN must be set in importer/.env")
    headers = {"X-Admin-Token": config.ADMIN_TOKEN}
    if data is not None:
        headers["Content-Type"] = "image/jpeg"
    last = None
    for attempt in range(RETRIES):
        try:
            answer = _http.request(method, f"{config.ADMIN_BASE}/api/pride-admin{path}", json=json, data=data,
                                   headers=headers, timeout=timeout)
        except requests.RequestException as error:
            last = type(error).__name__
        else:
            if answer.status_code < 500:
                try:
                    body = answer.json()
                except ValueError:
                    raise AdminError(f"{method} {path}: answered {answer.status_code} without JSON")
                if answer.status_code >= 400 or body.get("status") == "error":
                    raise AdminError(f"{method} {path} refused ({answer.status_code}): {body.get('message')}")
                return body
            last = f"HTTP {answer.status_code}"
        if attempt < RETRIES - 1:
            time.sleep(2 ** attempt)
    raise AdminError(f"{method} {path} failed after {RETRIES} tries ({last})")


def get(path):
    return _request("GET", path, timeout=60)


def post(path, payload, timeout=300):
    return _request("POST", path, json=payload, timeout=timeout)


def putBytes(path, data):
    return _request("PUT", path, data=data, timeout=60)
