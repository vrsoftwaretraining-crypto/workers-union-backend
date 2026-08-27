import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import create_app
from database.db import db as _db


@pytest.fixture()
def app():
    os.environ["FLASK_ENV"] = "testing"
    application = create_app("testing")
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db


def register_union(client, reg_no="UNI001", admin_username="admin1", admin_password="adminpass123"):
    return client.post("/register-union", data={
        "registration_no": reg_no,
        "name": "Test Workers Union",
        "address": "Test Street",
        "admin_username": admin_username,
        "admin_password": admin_password,
        "admin_full_name": "Admin One",
        "admin_phone": "9999999999",
    }, follow_redirects=True)


def api_login_admin(client, reg_no="UNI001", username="admin1", password="adminpass123"):
    resp = client.post("/api/login", json={
        "union_reg_no": reg_no, "username": username, "password": password
    })
    return resp.get_json()
