import io
import zipfile

from conftest import register_union, api_login_admin


def test_backup_contains_manifest(client, db):
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]

    resp = client.post("/admin/api/backup", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    assert "manifest.json" in zf.namelist()


def test_restore_rejects_foreign_zip(client, db):
    register_union(client)
    admin_data = api_login_admin(client)
    admin_token = admin_data["access_token"]

    fake_zip = io.BytesIO()
    with zipfile.ZipFile(fake_zip, "w") as zf:
        zf.writestr("manifest.json", '{"manifest": {"app": "not-our-app"}}')
    fake_zip.seek(0)

    resp = client.post(
        "/admin/api/restore",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"backup_file": (fake_zip, "fake.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
