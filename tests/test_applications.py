from tests.conftest import register

JOB = {"company": "Acme", "position": "Backend Intern", "location": "Hyderabad", "status": "applied"}


def test_create_and_get(client, auth):
    created = client.post("/applications", json=JOB, headers=auth)
    assert created.status_code == 201
    app_id = created.json()["id"]
    fetched = client.get(f"/applications/{app_id}", headers=auth)
    assert fetched.status_code == 200
    assert fetched.json()["company"] == "Acme"
    assert fetched.json()["has_resume"] is False


def test_user_can_have_many_applications(client, auth):
    for i in range(3):
        assert client.post("/applications", json={**JOB, "company": f"Co{i}"}, headers=auth).status_code == 201
    assert client.get("/applications", headers=auth).json()["total"] == 3


def test_update_fields_and_status(client, auth):
    app_id = client.post("/applications", json=JOB, headers=auth).json()["id"]
    res = client.put(f"/applications/{app_id}", json={"notes": "Referred by Sam"}, headers=auth)
    assert res.status_code == 200 and res.json()["notes"] == "Referred by Sam"
    res = client.patch(f"/applications/{app_id}/status", json={"status": "interviewing"}, headers=auth)
    assert res.status_code == 200 and res.json()["status"] == "interviewing"


def test_invalid_status_rejected(client, auth):
    app_id = client.post("/applications", json=JOB, headers=auth).json()["id"]
    res = client.patch(f"/applications/{app_id}/status", json={"status": "ghosted"}, headers=auth)
    assert res.status_code == 422


def test_filter_and_search(client, auth):
    client.post("/applications", json={**JOB, "company": "Google", "position": "SWE"}, headers=auth)
    client.post("/applications", json={**JOB, "company": "Zoho", "position": "Python Dev", "status": "offered"}, headers=auth)
    assert client.get("/applications?status=offered", headers=auth).json()["total"] == 1
    assert client.get("/applications?search=goog", headers=auth).json()["items"][0]["company"] == "Google"


def test_stats(client, auth):
    for status in ["applied", "applied", "interviewing", "offered", "rejected"]:
        client.post("/applications", json={**JOB, "status": status}, headers=auth)
    stats = client.get("/applications/stats", headers=auth).json()
    assert stats["total"] == 5
    assert stats["by_status"] == {"applied": 2, "interviewing": 1, "offered": 1, "rejected": 1}
    assert stats["active"] == 3
    assert stats["offer_rate"] == 20.0


def test_delete(client, auth):
    app_id = client.post("/applications", json=JOB, headers=auth).json()["id"]
    assert client.delete(f"/applications/{app_id}", headers=auth).status_code == 200
    assert client.get(f"/applications/{app_id}", headers=auth).status_code == 404


def test_users_cannot_access_each_others_data(client, auth):
    app_id = client.post("/applications", json=JOB, headers=auth).json()["id"]
    bob = register(client, email="bob@example.com", name="Bob")
    assert client.get(f"/applications/{app_id}", headers=bob).status_code == 404
    assert client.put(f"/applications/{app_id}", json={"notes": "hacked"}, headers=bob).status_code == 404
    assert client.delete(f"/applications/{app_id}", headers=bob).status_code == 404
    assert client.get("/applications", headers=bob).json()["total"] == 0


def test_malformed_id_is_rejected(client, auth):
    assert client.get("/applications/not-a-number", headers=auth).status_code == 422


def test_unknown_id_is_404(client, auth):
    assert client.get("/applications/99999", headers=auth).status_code == 404
