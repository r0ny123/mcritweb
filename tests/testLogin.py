#!/usr/bin/python
"""What a failed login is allowed to reveal.

`/login` is unauthenticated and unthrottled, so anything it says about *why* a login
failed is something a caller can ask for as many times as it likes. Saying "Incorrect
username." for one case and "Incorrect password." for the other answers "does this
account exist?" one request at a time. Issue #101.
"""

import logging
import unittest

import pytest
from werkzeug.security import generate_password_hash

from mcritweb.db import UserInfo

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

PASSWORD = "correct horse battery staple"


@pytest.fixture
def registered_user(app):
    """An account to fail to log into, so the app is past first-user registration."""
    with app.app_context():
        user_info = UserInfo()
        user_info.username = "alice"
        user_info.password = generate_password_hash(PASSWORD)
        user_info.role = "visitor"
        user_info.apitoken = "apitoken-alice"
        user_info.saveToDb()
    return "alice"


def attempt(client, username, password):
    return client.post("/login", data={"username": username, "inputPassword": password},
                       follow_redirects=True).get_data(as_text=True)


def test_a_wrong_password_and_an_unknown_user_give_the_same_message(client, registered_user):
    wrong_password = attempt(client, registered_user, "not the password")
    unknown_user = attempt(client, "nobody-by-that-name", "not the password")

    assert "Incorrect username or password." in wrong_password
    assert "Incorrect username or password." in unknown_user


def test_neither_message_names_which_half_was_wrong(client, registered_user):
    """The old strings, spelled out so this fails if either comes back."""
    for page in (attempt(client, registered_user, "not the password"),
                 attempt(client, "nobody-by-that-name", "not the password")):
        assert "Incorrect username." not in page
        assert "Incorrect password." not in page


def test_a_correct_login_still_works(client, registered_user):
    """The point of the above is not to make logging in harder."""
    response = client.post("/login", data={"username": registered_user, "inputPassword": PASSWORD})

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session.get("user_id") is not None


def test_an_unknown_username_costs_a_password_check(client, registered_user, monkeypatch):
    """The message alone does not close the hole.

    Password hashing is deliberately slow, so a branch that never reaches it answers
    measurably sooner and the timing says what the message will not. Asserting on the
    clock would be a flaky test; asserting that the hash function is *called* is the
    same claim without the flake.
    """
    from mcritweb.views import authentication

    checked = []
    real_check = authentication.check_password_hash
    monkeypatch.setattr(authentication, "check_password_hash",
                        lambda pwhash, password: checked.append(password) or real_check(pwhash, password))

    attempt(client, "nobody-by-that-name", "not the password")

    assert checked == ["not the password"], "no password check ran for an absent user"


def test_the_dummy_hash_never_admits_anyone():
    """It is a hash of a random secret, so nothing should verify against it - least of
    all the empty password, which is what an unauthenticated probe would send."""
    from werkzeug.security import check_password_hash

    from mcritweb.views import authentication

    authentication._spend_a_password_check("")

    assert authentication._ABSENT_USER_PASSWORD_HASH is not None
    for guess in ("", " ", "password", "admin"):
        assert not check_password_hash(authentication._ABSENT_USER_PASSWORD_HASH, guess)


if __name__ == "__main__":
    unittest.main()
