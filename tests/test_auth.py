from conftest import register_union, api_login_admin


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


def test_worker_self_registration_is_pending(client, db):
    register_union(client)
    resp = client.post("/api/register-worker", json={
        "union_reg_no": "UNI001",
        "username": "worker1",
        "password": "workerpass123",
        "full_name": "Worker One",
        "phone": "7777777777",
        "worker_type": "Plumber",
    })
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    login_resp = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "worker1", "password": "workerpass123"
    })
    assert login_resp.status_code == 403
    assert "approval" in login_resp.get_json()["message"].lower()


def test_admin_can_approve_worker_then_worker_can_login(client, db):
    register_union(client)
    client.post("/api/register-worker", json={
        "union_reg_no": "UNI001", "username": "worker1", "password": "workerpass123",
        "full_name": "Worker One", "phone": "7777777777",
    })
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]

    workers_resp = client.get("/admin/api/workers", headers={"Authorization": f"Bearer {admin_token}"})
    worker_id = workers_resp.get_json()["workers"][0]["id"]

    approve_resp = client.post(f"/admin/api/workers/{worker_id}/approve",
                                headers={"Authorization": f"Bearer {admin_token}"})
    assert approve_resp.get_json()["success"] is True

    login_resp = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "worker1", "password": "workerpass123"
    })
    assert login_resp.status_code == 200
    assert login_resp.get_json()["success"] is True


def test_invalid_login_rejected(client, db):
    register_union(client)
    resp = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "admin1", "password": "wrongpassword"
    })
    assert resp.status_code == 401
