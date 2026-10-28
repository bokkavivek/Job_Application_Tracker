from tests.conftest import register


def test_signup_duplicate_email_rejected(client):
    body = {"name": "A", "email": "a@example.com", "password": "password123"}
    assert client.post("/auth/signup", json=body).status_code == 201
    assert client.post("/auth/signup", json=body).status_code == 400


def test_short_password_rejected(client):
    res = client.post("/auth/signup", json={"name": "A", "email": "a@example.com", "password": "123"})
    assert res.status_code == 422


def test_login_blocked_until_email_verified(client):
    client.post("/auth/signup", json={"name": "A", "email": "a@example.com", "password": "password123"})
    res = client.post("/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert res.status_code == 403


def test_wrong_otp_rejected(client):
    client.post("/auth/signup", json={"name": "A", "email": "a@example.com", "password": "password123"})
    client.post("/auth/send-otp", json={"email": "a@example.com"})
    res = client.post("/auth/verify-otp", json={"email": "a@example.com", "otp": "000000"})
    assert res.status_code == 400


def test_wrong_password_rejected(client):
    register(client, email="b@example.com", password="password123")
    res = client.post("/auth/login", json={"email": "b@example.com", "password": "not-the-password"})
    assert res.status_code == 400


def test_me_returns_current_user(client, auth):
    res = client.get("/auth/me", headers=auth)
    assert res.status_code == 200
    assert res.json()["email"] == "alice@example.com"


def test_protected_routes_need_token(client):
    assert client.get("/applications").status_code == 401
    assert client.get("/applications", headers={"Authorization": "Bearer garbage"}).status_code == 401
