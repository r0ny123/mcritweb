"""Helpers for driving a live mcritweb instance: log in, read CSRF tokens, post forms."""
import re
import requests

USER, PASSWORD = "analyst1", "Passw0rd-live!"


def csrf(html):
    match = re.search(r'name="csrf-token" content="([^"]+)"', html) or re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1)


def login(base, user=USER, password=PASSWORD):
    s = requests.Session()
    page = s.get(f"{base}/login").text
    r = s.post(f"{base}/login", data={"csrf_token": csrf(page), "username": user, "inputPassword": password}, allow_redirects=False)
    assert r.status_code == 302 and "login" not in r.headers.get("Location", ""), (r.status_code, r.headers.get("Location"))
    s.base = base
    return s


def token(s, path="/"):
    return csrf(s.get(f"{s.base}{path}").text)
