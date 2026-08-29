from conftest import register_union, api_login_admin, api_admin_add_worker


def _worker_token(client, username="worker1"):
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]
    api_admin_add_worker(client, admin_token, username=username)
    login_resp = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": username, "password": "workerpass123"
    })
    return login_resp.get_json()["access_token"], admin_token


def test_worker_can_submit_claim(client, db):
    token, _ = _worker_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/claims", headers=headers, json={
        "claim_type": "Accident",
        "description": "Fell from scaffolding, need medical compensation.",
        "amount_requested": 15000,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["claim"]["status"] == "Submitted"

    list_resp = client.get("/api/claims", headers=headers)
    claims = list_resp.get_json()["claims"]
    assert len(claims) == 1
    assert claims[0]["claim_type"] == "Accident"


def test_admin_can_approve_and_mark_claim_paid(client, db):
    token, admin_token = _worker_token(client)
    worker_headers = {"Authorization": f"Bearer {token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    submit_resp = client.post("/api/claims", headers=worker_headers, json={
        "claim_type": "Insurance", "description": "Annual health insurance claim.",
        "amount_requested": 8000,
    })
    claim_id = submit_resp.get_json()["claim"]["id"]

    update_resp = client.post(f"/admin/api/claims/{claim_id}/update", headers=admin_headers, json={
        "status": "Paid", "amount_approved": 7500,
        "payment_date": "2026-08-20", "payment_reference": "TXN12345",
    })
    assert update_resp.status_code == 200
    updated = update_resp.get_json()["claim"]
    assert updated["status"] == "Paid"
    assert updated["amount_approved"] == 7500

    worker_view = client.get("/api/claims", headers=worker_headers).get_json()["claims"][0]
    assert worker_view["status"] == "Paid"
    assert worker_view["payment_reference"] == "TXN12345"


def test_admin_can_list_claims_filtered_by_status(client, db):
    token, admin_token = _worker_token(client)
    worker_headers = {"Authorization": f"Bearer {token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    client.post("/api/claims", headers=worker_headers, json={
        "claim_type": "Insurance", "description": "Claim A",
    })
    resp = client.get("/admin/api/claims?status=Submitted", headers=admin_headers)
    claims = resp.get_json()["claims"]
    assert len(claims) == 1
    assert claims[0]["status"] == "Submitted"


def test_worker_cannot_access_admin_claims_api(client, db):
    token, _ = _worker_token(client)
    resp = client.get("/admin/api/claims", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
