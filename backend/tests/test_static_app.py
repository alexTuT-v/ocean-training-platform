from fastapi.testclient import TestClient

from backend.app.main import create_app


ALICE = {"X-Actor-Email": "alice@east.test"}


def test_spa_routes_and_api_do_not_shadow_each_other(seeded_db, tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text('<html><div id="root">Training Admin</div></html>')
    (assets / "main.js").write_text('console.log("training")')
    client = TestClient(create_app(seeded_db, frontend_dist=dist))
    for path in ("/", "/certificates", "/certificates?search=Alex", "/courses"):
        response = client.get(path)
        assert response.status_code == 200
        assert "Training Admin" in response.text
        assert response.headers["content-type"].startswith("text/html")
    asset = client.get("/assets/main.js")
    assert asset.status_code == 200
    assert 'console.log("training")' in asset.text

    me = client.get("/api/me", headers=ALICE)
    assert me.status_code == 200
    assert me.headers["content-type"].startswith("application/json")
    exported = client.get("/api/certificates/export", headers=ALICE)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    missing_api = client.get("/api/does-not-exist", headers=ALICE)
    assert missing_api.status_code == 404
    assert set(missing_api.json()) == {"code", "message"}
