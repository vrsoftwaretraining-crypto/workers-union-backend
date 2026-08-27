from conftest import register_union, api_login_admin


def _register_and_approve_worker(client, username="worker1"):
    register_union(client)
    client.post("/api/register-worker", json={
        "union_reg_no": "UNI001", "username": username, "password": "workerpass123",
        "full_name": "Worker One", "phone": "7777777777", "worker_type": "Electrician",
    })
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]
    workers_resp = client.get("/admin/api/workers", headers={"Authorization": f"Bearer {admin_token}"})
    worker_id = workers_resp.get_json()["workers"][0]["id"]
    client.post(f"/admin/api/workers/{worker_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})

    login_resp = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": username, "password": "workerpass123"
    })
    return login_resp.get_json()["access_token"]


def test_worker_can_add_and_list_transactions(client, db):
    token = _register_and_approve_worker(client)
    headers = {"Authorization": f"Bearer {token}"}

    add_resp = client.post("/api/transactions", headers=headers, json={
        "kind": "Income", "category": "Daily wage", "amount": 800,
        "transaction_date": "2026-08-01", "notes": "Site A",
    })
    assert add_resp.status_code == 200
    assert add_resp.get_json()["success"] is True

    list_resp = client.get("/api/transactions", headers=headers)
    entries = list_resp.get_json()["entries"]
    assert len(entries) == 1
    assert entries[0]["amount"] == 800


def test_worker_directory_hides_sensitive_fields(client, db):
    token = _register_and_approve_worker(client, username="worker1")
    # Register + approve a second worker so the directory has 2 approved workers
    client.post("/api/register-worker", json={
        "union_reg_no": "UNI001", "username": "worker2", "password": "workerpass123",
        "full_name": "Worker Two", "phone": "6666666666",
        "bank_account_no": "123456789012",
    })
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]
    workers_resp = client.get("/admin/api/workers", headers={"Authorization": f"Bearer {admin_token}"})
    worker2_id = [w for w in workers_resp.get_json()["workers"] if w["role"] != "admin" and w["bank_account_no"] == "123456789012"][0]["id"]
    client.post(f"/admin/api/workers/{worker2_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})

    headers = {"Authorization": f"Bearer {token}"}
    directory_resp = client.get("/api/members", headers=headers)
    members = directory_resp.get_json()["members"]
    assert len(members) >= 1
    for m in members:
        assert "bank_account_no" not in m
        assert "health_card_no" not in m
        assert "insurance_policy_no" not in m


def test_notification_created_by_admin_visible_to_worker(client, db):
    token = _register_and_approve_worker(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]

    notif_resp = client.post("/admin/api/notifications", headers={"Authorization": f"Bearer {admin_token}"}, json={
        "title": "Monthly Meeting", "body": "Meeting on Sunday at 10am.", "category": "meeting",
    })
    assert notif_resp.get_json()["success"] is True

    worker_headers = {"Authorization": f"Bearer {token}"}
    list_resp = client.get("/api/notifications", headers=worker_headers)
    notifications = list_resp.get_json()["notifications"]
    assert len(notifications) == 1
    assert notifications[0]["title"] == "Monthly Meeting"
    assert notifications[0]["is_read"] is False

    mark_resp = client.post(f"/api/notifications/{notifications[0]['id']}/read", headers=worker_headers)
    assert mark_resp.get_json()["success"] is True


def test_work_entry_crud(client, db):
    token = _register_and_approve_worker(client)
    headers = {"Authorization": f"Bearer {token}"}

    add_resp = client.post("/api/work-entries", headers=headers, json={
        "work_date": "2026-08-10", "description": "Wiring repair", "hours_worked": 6,
    })
    entry_id = add_resp.get_json()["entry"]["id"]

    list_resp = client.get("/api/work-entries", headers=headers)
    assert len(list_resp.get_json()["entries"]) == 1

    del_resp = client.delete(f"/api/work-entries/{entry_id}", headers=headers)
    assert del_resp.get_json()["success"] is True

    list_resp2 = client.get("/api/work-entries", headers=headers)
    assert len(list_resp2.get_json()["entries"]) == 0
