from conftest import register_union, api_login_admin, api_admin_add_worker


def test_register_union_and_admin_login(client, db):
    register_union(client)
    data = api_login_admin(client)
    assert data["success"] is True
    assert data["user"]["role"] == "admin"
    assert "access_token" in data


def test_duplicate_union_registration_fails(client, db):
    register_union(client)
    resp = client.post("/register-union", data={
        "registration_no": "UNI001",
        "name": "Another Union",
        "admin_username": "admin2",
        "admin_password": "adminpass123",
        "admin_full_name": "Admin Two",
        "admin_phone": "8888888888",
    }, follow_redirects=True)
    assert b"already exists" in resp.data


def test_admin_created_worker_is_approved_immediately(client, db):
    """Self-registration was removed -- only admins can create workers now,
    and an admin-created account is approved right away (no pending queue),
    since the admin has already verified the person in person."""
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]

    add_resp = api_admin_add_worker(client, admin_token, username="worker1")
    assert add_resp["success"] is True
    assert add_resp["worker"]["status"] == "approved"

    login_resp = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "worker1", "password": "workerpass123"
    })
    assert login_resp.status_code == 200
    assert login_resp.get_json()["success"] is True


def test_duplicate_username_in_same_union_rejected(client, db):
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]

    api_admin_add_worker(client, admin_token, username="worker1")
    dup_resp = api_admin_add_worker(client, admin_token, username="worker1")
    assert dup_resp["success"] is False


def test_worker_cannot_add_other_workers(client, db):
    """Only admins can hit /admin/api/workers -- a worker's own token must
    be rejected."""
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]
    api_admin_add_worker(client, admin_token, username="worker1")

    worker_login = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "worker1", "password": "workerpass123"
    }).get_json()
    worker_token = worker_login["access_token"]

    resp = client.post("/admin/api/workers", headers={"Authorization": f"Bearer {worker_token}"}, json={
        "username": "worker2", "password": "pass123456", "full_name": "Worker Two", "phone": "6666666666",
    })
    assert resp.status_code == 403


def test_invalid_login_rejected(client, db):
    register_union(client)
    resp = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "admin1", "password": "wrongpassword"
    })
    assert resp.status_code == 401
