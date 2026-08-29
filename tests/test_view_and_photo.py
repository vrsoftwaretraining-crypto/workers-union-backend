import os

from conftest import register_union, api_login_admin, api_admin_add_worker
from models.user import User
from database.db import db


def test_admin_view_worker_page_shows_sensitive_fields(client, db):
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]
    add_resp = api_admin_add_worker(client, admin_token, username="worker1",
                                     aadhar_no="1234 5678 9012", pan_no="ABCDE1234F")
    worker_id = add_resp["worker"]["id"]

    login_resp = client.post("/login", data={
        "union_reg_no": "UNI001", "username": "admin1", "password": "adminpass123",
    }, follow_redirects=True)

    resp = client.get(f"/admin/workers/{worker_id}/view")
    assert resp.status_code == 200
    assert b"1234 5678 9012" in resp.data
    assert b"ABCDE1234F" in resp.data


def test_worker_photo_served_to_fellow_member_only(client, db, app):
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]

    add_resp1 = api_admin_add_worker(client, admin_token, username="worker1")
    add_resp2 = api_admin_add_worker(client, admin_token, username="worker2", phone="6666666666")
    worker1_id = add_resp1["worker"]["id"]

    # Simulate an already-uploaded photo file on disk + DB pointer to it.
    with app.app_context():
        w1 = User.query.get(worker1_id)
        upload_dir = os.path.join(app.config["UPLOAD_DIR"], "UNI001", str(worker1_id))
        os.makedirs(upload_dir, exist_ok=True)
        photo_path = os.path.join(upload_dir, "photo_test.jpg")
        with open(photo_path, "wb") as f:
            f.write(b"fake-image-bytes")
        w1.photo_file = f"UNI001/{worker1_id}/photo_test.jpg"
        db.session.commit()

    worker2_login = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "worker2", "password": "workerpass123",
    }).get_json()
    worker2_token = worker2_login["access_token"]

    resp = client.get(f"/api/members/{worker1_id}/photo",
                       headers={"Authorization": f"Bearer {worker2_token}"})
    assert resp.status_code == 200
    assert resp.data == b"fake-image-bytes"


def test_directory_now_includes_address_and_photo_but_not_bank(client, db):
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]
    api_admin_add_worker(client, admin_token, username="worker1", address="12 Main Street")
    api_admin_add_worker(client, admin_token, username="worker2", phone="6666666666")

    worker_login = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "worker2", "password": "workerpass123",
    }).get_json()
    headers = {"Authorization": f"Bearer {worker_login['access_token']}"}

    resp = client.get("/api/members", headers=headers)
    members = resp.get_json()["members"]
    worker1 = next(m for m in members if m["full_name"] == "Worker One")
    assert worker1["address"] == "12 Main Street"
    assert "photo_file" in worker1
    assert "bank_account_no" not in worker1
