import pytest
from bloggr.db import get_db


def test_index(client, auth):
    response = client.get("/")
    assert b"Log In" in response.data
    assert b"Register" in response.data

    auth.login()
    response = client.get("/")
    assert b"Log Out" in response.data
    assert b"test title" in response.data       
    assert b"by test on 2026-01-01" in response.data 
    assert b"test\nbody" in response.data   
    assert b"href=\"/1/update\"" in response.data 

    
@pytest.mark.parametrize("path", (
    "/create",
    '/1/update',
    "/1/delete",
))
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers["Location"] == "/auth/login"

def test_author_required(app, client, auth):
    auth.login()
    assert client.get("/create").status_code == 200
    client.post("/1/update", data={"title": "updated", "body": ""})

    with app.app_context():
        db = get_db()
        post = db.execute("SELECT * FROM post WHERE id = 1").fetchone()
        assert post["title"] == "updated"


@pytest.mark.parametrize("path", (
    "/create",
    "/1/update",
))
def test_create_update_validate(client, auth, path):
    auth.login()
    response = client.post(path, data = {"title": "", "body": ""})
    assert b"Title is required!" in response.data


def test_delete(client, auth, app):
    auth.login()
    response = client.post("/1/delete")
    assert response.headers["Location"] == "/"

    with app.app_context():
        db = get_db()
        post = db.execute("SELECT * FROM post WHERE id = 1").fetchone()
        assert post is None

