"""These tests exercise the FarmProfit-style recommendation/report helpers
kept for the worker's own income/expense reports (PDF/Excel export)."""
from conftest import register_union, api_login_admin


def _login_worker(client):
    register_union(client)
    client.post("/api/register-worker", json={
        "union_reg_no": "UNI001", "username": "worker1", "password": "workerpass123",
        "full_name": "Worker One", "phone": "7777777777",
    })
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]
    workers_resp = client.get("/admin/api/workers", headers={"Authorization": f"Bearer {admin_token}"})
    worker_id = workers_resp.get_json()["workers"][0]["id"]
    client.post(f"/admin/api/workers/{worker_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    login_resp = client.post("/api/login", json={
        "union_reg_no": "UNI001", "username": "worker1", "password": "workerpass123"
    })
    return login_resp.get_json()["access_token"]


def test_pdf_export_returns_pdf(client, db):
    token = _login_worker(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/transactions", headers=headers, json={
        "kind": "Income", "category": "Wage", "amount": 500, "transaction_date": "2026-08-01"
    })
    resp = client.get("/api/reports/export/pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"


def test_excel_export_returns_xlsx(client, db):
    token = _login_worker(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/reports/export/excel", headers=headers)
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.mimetype
