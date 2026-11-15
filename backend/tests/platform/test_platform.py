# tests/platform/test_platform.py
#
# The platform (advanced_reports/): encryption, per-church storage, sessions,
# the API, and a run from button press to downloadable PDFs. Everything runs
# against an in-memory store and the made-up demo church; nothing touches
# Planning Center or Google.
#
# The isolation tests are the important ones (plan §3.7): two churches in one
# service, and neither can read, list, change, run or download the other's.

import time

import pytest
from fastapi.testclient import TestClient

from advanced_reports import demo, runner
from advanced_reports.app import create_app
from advanced_reports.core import connections, crypto, pco_oauth, session
from advanced_reports.core.store import FileStore, MemoryStore
from advanced_reports.core.tenant_repo import TenantRepo
from advanced_reports.modules import checkin_reports
from advanced_reports.settings import Settings, from_env

CSRF = {"X-AR-CSRF": "1"}


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, master_key_b64=crypto.Vault.generate_b64(),
                    session_secret="test-session-secret", dev_login=True)


@pytest.fixture
def store():
    return MemoryStore()


class InlineLauncher:
    """Runs the runner in-process, immediately, instead of a subprocess."""

    def __init__(self, settings, store):
        self.settings, self.store, self.launched = settings, store, []

    def launch(self, org_id, run_id):
        self.launched.append((org_id, run_id))
        runner.execute(self.settings, self.store, org_id, run_id)


@pytest.fixture
def launcher(settings, store):
    return InlineLauncher(settings, store)


@pytest.fixture
def app(settings, store, launcher):
    return create_app(settings, store, launcher)


def repo(settings, store, org_id):
    return TenantRepo(store, settings.vault, settings.files_dir, org_id)


def make_church(settings, store, org_id, name):
    """A second church with the demo connection, set up directly in the store."""
    r = repo(settings, store, org_id)
    r.create_church(name=name, timezone="America/Chicago", language="es")
    r.save_module(checkin_reports.MODULE_ID, {"reports": demo.REPORTS[1:]})
    r.save_secret("pco", {"kind": "demo"}, kind="demo", status="connected")
    return r


def client_for(app, settings, org_id) -> TestClient:
    client = TestClient(app)
    client.cookies.set(session.COOKIE, session.issue(settings.session_secret, org_id=org_id,
                                                     person_id="p1", name="Admin"))
    return client


# ── Encryption ────────────────────────────────────────────────────────────────

class TestCrypto:
    def test_round_trip(self):
        vault = crypto.Vault.from_b64(crypto.Vault.generate_b64())
        key = vault.unwrap(vault.new_wrapped_key("100"), "100")
        assert crypto.unseal(key, crypto.seal(key, {"token": "abc"}, "x"), "x") == {"token": "abc"}

    def test_ciphertext_does_not_contain_the_secret(self):
        vault = crypto.Vault.from_b64(crypto.Vault.generate_b64())
        key = vault.unwrap(vault.new_wrapped_key("100"), "100")
        assert "hunter2" not in crypto.seal(key, {"secret": "hunter2"}, "x")

    def test_a_blob_moved_to_another_place_does_not_open(self):
        vault = crypto.Vault.from_b64(crypto.Vault.generate_b64())
        key = vault.unwrap(vault.new_wrapped_key("100"), "100")
        with pytest.raises(crypto.DecryptError):
            crypto.unseal(key, crypto.seal(key, {"a": 1}, "churches/100/connections/pco"),
                          "churches/200/connections/pco")

    def test_one_churchs_key_cannot_be_unwrapped_as_anothers(self):
        vault = crypto.Vault.from_b64(crypto.Vault.generate_b64())
        with pytest.raises(crypto.DecryptError):
            vault.unwrap(vault.new_wrapped_key("100"), "200")

    def test_a_different_master_key_opens_nothing(self):
        wrapped = crypto.Vault.from_b64(crypto.Vault.generate_b64()).new_wrapped_key("100")
        with pytest.raises(crypto.DecryptError):
            crypto.Vault.from_b64(crypto.Vault.generate_b64()).unwrap(wrapped, "100")


# ── Storage ───────────────────────────────────────────────────────────────────

@pytest.fixture(params=["memory", "file"])
def any_store(request, tmp_path):
    return MemoryStore() if request.param == "memory" else FileStore(tmp_path / "store")


class TestStores:
    def test_get_set_list_delete(self, any_store):
        any_store.set("churches/1", {"name": "Uno"})
        any_store.set("churches/1/runs/a", {"id": "a"})
        any_store.set("churches/1/runs/b", {"id": "b"})
        any_store.set("churches/2/runs/z", {"id": "z"})
        assert any_store.get("churches/1") == {"name": "Uno"}
        assert any_store.get("churches/9") is None
        assert [p for p, _ in any_store.list("churches/1/runs")] == ["churches/1/runs/a", "churches/1/runs/b"]
        any_store.delete_tree("churches/1")
        assert any_store.get("churches/1") is None and any_store.list("churches/1/runs") == []
        assert any_store.get("churches/2/runs/z") == {"id": "z"}

    @pytest.mark.parametrize("path", ["churches/../x", "churches/1/runs", "/etc/passwd", "churches/a b", ""])
    def test_bad_paths_are_refused(self, any_store, path):
        with pytest.raises(ValueError):
            any_store.set(path, {})


class TestTenantRepo:
    @pytest.mark.parametrize("org_id", ["", "../1", "1/2", "a b", "x" * 80])
    def test_bad_church_ids_are_refused(self, settings, store, org_id):
        with pytest.raises(ValueError):
            repo(settings, store, org_id)

    def test_every_document_sits_under_the_church(self, settings, store):
        r = make_church(settings, store, "100", "Uno")
        r.touch_member("p1", "Ana")
        r.save_run(r.create_run("manual"))
        assert store.docs and all(p == "churches/100" or p.startswith("churches/100/") for p in store.docs)

    def test_secrets_are_stored_encrypted_and_read_back(self, settings, store):
        r = make_church(settings, store, "100", "Uno")
        r.save_secret("pco", {"kind": "pat", "app_id": "id-123", "secret": "s3cret-value"}, kind="pat")
        assert "s3cret-value" not in str(store.docs) and "id-123" not in str(store.docs)
        assert r.secret("pco")["secret"] == "s3cret-value"
        assert r.connection("pco") == {"kind": "pat", "updated_at": r.connection("pco")["updated_at"]}

    def test_a_secret_copied_into_another_church_cannot_be_read(self, settings, store):
        a, b = make_church(settings, store, "100", "Uno"), make_church(settings, store, "200", "Dos")
        a.save_secret("pco", {"kind": "pat", "secret": "a-secret"}, kind="pat")
        store.docs["churches/200/connections/pco"] = store.docs["churches/100/connections/pco"]
        with pytest.raises(crypto.DecryptError):
            b.secret("pco")

    def test_run_files_cannot_escape_the_run_folder(self, settings, store):
        r = make_church(settings, store, "100", "Uno")
        folder = r.run_dir("run1")
        (folder / "Roster.pdf").write_bytes(b"%PDF")
        (settings.files_dir / "secret.pdf").write_bytes(b"%PDF")
        assert r.run_file("run1", "Roster.pdf") is not None
        assert r.run_file("run1", "../../../../secret.pdf") is None
        assert r.run_file("../../200/runs/run1", "Roster.pdf") is None

    def test_delete_everything_leaves_nothing(self, settings, store):
        a, b = make_church(settings, store, "100", "Uno"), make_church(settings, store, "200", "Dos")
        a.touch_member("p1", "Ana")
        run = a.create_run("manual")
        (a.run_dir(run["id"]) / "Roster.pdf").write_bytes(b"%PDF")
        a.save_logo(b"png")
        a.delete_everything()
        assert not [p for p in store.docs if p.startswith("churches/100")]
        assert not (settings.files_dir / "churches" / "100").exists()
        assert b.exists() and b.secret("pco") == {"kind": "demo"}

    def test_only_one_active_run(self, settings, store):
        r = make_church(settings, store, "100", "Uno")
        assert r.active_run() is None
        run = r.create_run("manual")
        assert r.active_run()["id"] == run["id"]
        run["status"] = "succeeded"
        r.save_run(run)
        assert r.active_run() is None

    def test_a_run_stuck_for_too_long_stops_blocking(self, settings, store):
        r = make_church(settings, store, "100", "Uno")
        run = r.create_run("manual")
        run["created_at"] = "2020-01-01T00:00:00Z"
        r.save_run(run)
        assert r.active_run() is None


# ── Sessions ──────────────────────────────────────────────────────────────────

class TestSession:
    def test_round_trip(self):
        cookie = session.issue("k", org_id="100", person_id="p", name="Ana")
        assert session.read("k", cookie)["org"] == "100"

    def test_forged_tampered_and_expired_cookies_are_refused(self):
        cookie = session.issue("k", org_id="100", person_id="p", name="Ana")
        body, signature = cookie.split(".")
        other = session.issue("k", org_id="200", person_id="p", name="Ana").split(".")[0]
        assert session.read("another-secret", cookie) is None
        assert session.read("k", f"{other}.{signature}") is None      # body swapped to another church
        assert session.read("k", body) is None
        assert session.read("k", "") is None and session.read("k", None) is None
        assert session.read("k", cookie, now=time.time() + session.MAX_AGE + 5) is None


class TestSettings:
    def test_production_refuses_to_invent_keys(self, tmp_path):
        with pytest.raises(RuntimeError):
            from_env({"AR_DATA_DIR": str(tmp_path)})

    def test_dev_generates_and_reuses_keys(self, tmp_path):
        env = {"AR_DATA_DIR": str(tmp_path), "AR_DEV_LOGIN": "1"}
        assert from_env(env).master_key_b64 == from_env(env).master_key_b64


# ── The API ───────────────────────────────────────────────────────────────────

class TestSignIn:
    def test_everything_needs_a_session(self, app):
        client = TestClient(app)
        for path in ("/api/me", "/api/church", "/api/modules/checkin_reports", "/api/runs",
                     "/api/runs/x", "/api/runs/x/files/Roster.pdf", "/api/pco/events"):
            assert client.get(path).status_code == 401, path
        for path in ("/api/runs", "/api/disconnect"):
            assert client.post(path, headers=CSRF).status_code == 401, path

    def test_dev_login_creates_the_demo_church(self, app):
        client = TestClient(app)
        assert client.get("/api/auth/config").json()["dev_churches"][0]["id"] == "demo"
        assert client.post("/auth/dev/login", json={"church": "demo"}, headers=CSRF).status_code == 200
        me = client.get("/api/me").json()
        assert me["church"]["name"] == "Liberty Baptist Church"
        assert me["connections"]["pco"]["kind"] == "demo"
        assert "sealed" not in str(me)

    def test_dev_login_is_off_unless_enabled(self, settings, store, launcher):
        off = Settings(data_dir=settings.data_dir, master_key_b64=settings.master_key_b64,
                       session_secret="s", dev_login=False)
        client = TestClient(create_app(off, store, launcher))
        assert client.get("/api/auth/config").json() == {"pco_oauth": False, "dev_churches": []}
        assert client.post("/auth/dev/login", json={"church": "demo"}, headers=CSRF).status_code == 404
        assert client.get("/auth/pco/login").status_code == 404

    def test_the_demo_connection_does_nothing_outside_dev(self, settings, store):
        make_church(settings, store, "100", "Uno")
        off = Settings(data_dir=settings.data_dir, master_key_b64=settings.master_key_b64,
                       session_secret="s", dev_login=False)
        with pytest.raises(connections.NotConnected):
            connections.pco_client(repo(off, store, "100"), off)

    def test_changes_need_the_csrf_header(self, app, settings, store):
        make_church(settings, store, "100", "Uno")
        client = client_for(app, settings, "100")
        assert client.post("/api/runs").status_code == 403
        assert client.put("/api/church", json={"name": "X"}).status_code == 403
        assert client.post("/api/disconnect").status_code == 403
        assert repo(settings, store, "100").church()["name"] == "Uno"

    def test_a_session_for_a_deleted_church_is_signed_out(self, app, settings):
        assert client_for(app, settings, "999").get("/api/me").status_code == 401

    def test_callback_refuses_a_missing_or_wrong_state(self, settings, store, launcher):
        on = Settings(data_dir=settings.data_dir, master_key_b64=settings.master_key_b64,
                      session_secret="s", pco_client_id="cid", pco_client_secret="sec")
        client = TestClient(create_app(on, store, launcher), follow_redirects=False)
        login = client.get("/auth/pco/login")
        assert login.status_code == 307 and "client_id=cid" in login.headers["location"]
        assert "scope=people+check_ins" in login.headers["location"]
        assert client.get("/auth/pco/callback?code=abc&state=wrong").status_code == 400
        assert TestClient(create_app(on, store, launcher)).get("/auth/pco/callback?code=abc&state=x").status_code == 400


class TestChurchSettings:
    def test_update_and_validation(self, app, settings, store):
        make_church(settings, store, "100", "Uno")
        client = client_for(app, settings, "100")
        ok = client.put("/api/church", headers=CSRF, json={
            "name": "Iglesia Uno", "timezone": "America/Denver", "language": "en", "theme": "verano",
            "branding": {"verse_text": "Hola", "feedback_url": "https://example.org/f"}})
        assert ok.status_code == 200 and ok.json()["theme"] == "verano"
        assert ok.json()["branding"]["verse_text"] == "Hola"
        for bad in ({"timezone": "Mars/Olympus"}, {"language": "fr"}, {"theme": "disco"}, {"name": "  "},
                    {"branding": {"feedback_url": "javascript:alert(1)"}}, {"branding": {"logo_path": "/etc"}}):
            assert client.put("/api/church", headers=CSRF, json=bad).status_code == 422, bad
        assert "wrapped_data_key" not in client.get("/api/church").json()

    def test_reports_are_validated_by_the_engine(self, app, settings, store):
        make_church(settings, store, "100", "Uno")
        client = client_for(app, settings, "100")
        good = [{"id": "kids", "label": "Kids", "pco_event": "Kids", "start_date": "2026-08-23"}]
        saved = client.put("/api/modules/checkin_reports", headers=CSRF, json={"reports": good})
        assert saved.status_code == 200 and saved.json()["reports"][0]["start_date"] == "2026-08-23"
        assert client.get("/api/modules/checkin_reports").json() == saved.json()
        for bad in ([{"id": "x", "label": "X"}], [{"id": "x", "label": "X", "pco_event": "X", "nope": 1}],
                    good + good, [{"id": "x", "label": "X", "pco_event": "X", "show_route": True}]):
            assert client.put("/api/modules/checkin_reports", headers=CSRF, json={"reports": bad}).status_code == 422

    def test_events_and_locations_come_from_the_churchs_connection(self, app, settings, store):
        make_church(settings, store, "100", "Uno")
        client = client_for(app, settings, "100")
        events = client.get("/api/pco/events").json()["events"]
        assert [e["name"] for e in events] == ["Sunday School", "Bus Routes"]
        locations = client.get(f"/api/pco/events/{events[0]['id']}/locations").json()["locations"]
        assert "Nursery" in [loc["name"] for loc in locations]


class TestRuns:
    def test_run_now_makes_downloadable_pdfs(self, app, launcher):
        client = TestClient(app)
        client.post("/auth/dev/login", json={"church": "demo"}, headers=CSRF)
        started = client.post("/api/runs", headers=CSRF)
        assert started.status_code == 202
        run = client.get(f"/api/runs/{started.json()['id']}").json()
        assert run["status"] == "succeeded", run["log"][-5:]
        assert run["error"] is None and run["timings"]["total_s"] > 0
        paths = [o["path"] for o in run["outputs"]]
        assert "Sunday_School/Nursery/Roster.pdf" in paths
        assert "Volunteers/Bus_Routes/Volunteers.pdf" in paths
        assert "Sunday_School/Nursery/Instructions.pdf" in paths
        assert run["usage"]["files"] == len(paths) == 12
        assert any("Saved Sunday School/Nursery/Roster.pdf" in line for line in run["log"])
        pdf = client.get(f"/api/runs/{run['id']}/files/Sunday_School/Nursery/Roster.pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        assert pdf.headers["content-type"] == "application/pdf"
        listed = client.get("/api/runs").json()["runs"]
        assert listed[0]["id"] == run["id"] and "log" not in listed[0] and listed[0]["files"] == 12
        assert launcher.launched == [(demo.ORG_ID, run["id"])]

    def test_the_log_never_shows_server_paths(self, app, settings):
        client = TestClient(app)
        client.post("/auth/dev/login", json={"church": "demo"}, headers=CSRF)
        run = client.get(f"/api/runs/{client.post('/api/runs', headers=CSRF).json()['id']}").json()
        assert str(settings.data_dir) not in "\n".join(run["log"])

    def test_no_reports_means_no_run(self, app, settings, store):
        r = make_church(settings, store, "100", "Uno")
        r.save_module(checkin_reports.MODULE_ID, {"reports": []})
        assert client_for(app, settings, "100").post("/api/runs", headers=CSRF).status_code == 409

    def test_second_run_is_refused_while_one_is_active(self, settings, store):
        class Never:
            def launch(self, *_):
                pass
        make_church(settings, store, "100", "Uno")
        client = client_for(create_app(settings, store, Never()), settings, "100")
        assert client.post("/api/runs", headers=CSRF).status_code == 202
        assert client.post("/api/runs", headers=CSRF).status_code == 409

    def test_a_failing_run_ends_as_failed_with_a_reason(self, settings, store):
        r = make_church(settings, store, "100", "Uno")
        r.save_secret("pco", {"kind": "mystery"}, kind="mystery")
        run = r.create_run("manual")
        assert runner.execute(settings, store, "100", run["id"]) is False
        done = r.run(run["id"])
        assert done["status"] == "failed" and "mystery" in done["error"] and done["finished_at"]

    def test_runner_command_line_needs_two_arguments(self, capsys):
        assert runner.main([]) == 2


# ── Two churches in one service ───────────────────────────────────────────────

class TestTwoChurchIsolation:
    @pytest.fixture
    def two(self, app, settings, store):
        a = TestClient(app)
        a.post("/auth/dev/login", json={"church": "demo"}, headers=CSRF)           # Liberty (English)
        make_church(settings, store, "200", "Iglesia Dos")                        # Spanish, bus routes only
        b = client_for(app, settings, "200")
        run_a = a.post("/api/runs", headers=CSRF).json()["id"]
        run_b = b.post("/api/runs", headers=CSRF).json()["id"]
        return a, b, run_a, run_b

    def test_each_sees_only_its_own_church_and_reports(self, two):
        a, b, *_ = two
        assert a.get("/api/me").json()["church"]["name"] == "Liberty Baptist Church"
        assert b.get("/api/me").json()["church"]["name"] == "Iglesia Dos"
        assert len(a.get("/api/modules/checkin_reports").json()["reports"]) == 2
        assert len(b.get("/api/modules/checkin_reports").json()["reports"]) == 1

    def test_runs_cannot_be_listed_read_or_downloaded_across_churches(self, two):
        a, b, run_a, run_b = two
        assert [r["id"] for r in a.get("/api/runs").json()["runs"]] == [run_a]
        assert [r["id"] for r in b.get("/api/runs").json()["runs"]] == [run_b]
        assert a.get(f"/api/runs/{run_b}").status_code == 404
        assert b.get(f"/api/runs/{run_a}").status_code == 404
        own = a.get(f"/api/runs/{run_a}").json()["outputs"][0]["path"]
        assert a.get(f"/api/runs/{run_a}/files/{own}").status_code == 200
        assert b.get(f"/api/runs/{run_a}/files/{own}").status_code == 404
        theirs = b.get(f"/api/runs/{run_b}").json()["outputs"][0]["path"]
        assert a.get(f"/api/runs/{run_b}/files/{theirs}").status_code == 404
        assert a.get(f"/api/runs/{run_a}/files/../../../200/runs/{run_b}/{theirs}").status_code == 404

    def test_each_run_used_its_own_churchs_language_and_reports(self, two):
        a, b, run_a, run_b = two
        files_a = [o["path"] for o in a.get(f"/api/runs/{run_a}").json()["outputs"]]
        files_b = [o["path"] for o in b.get(f"/api/runs/{run_b}").json()["outputs"]]
        assert any(p.endswith("Volunteers.pdf") for p in files_a) and not any("Voluntarios" in p for p in files_a)
        assert any(p.endswith("Voluntarios.pdf") for p in files_b) and not any("Sunday_School" in p for p in files_b)

    def test_changes_and_disconnect_touch_only_your_own_church(self, two, settings, store):
        a, b, run_a, run_b = two
        b.put("/api/church", headers=CSRF, json={"name": "Renombrada"})
        assert a.get("/api/me").json()["church"]["name"] == "Liberty Baptist Church"
        assert b.post("/api/disconnect", headers=CSRF).status_code == 200
        assert not [p for p in store.docs if p.startswith("churches/200")]
        assert not (settings.files_dir / "churches" / "200").exists()
        assert b.get("/api/me").status_code == 401
        assert a.get(f"/api/runs/{run_a}").status_code == 200
        assert a.get("/api/me").json()["connections"]["pco"]["kind"] == "demo"

    def test_no_identifier_in_a_request_can_select_another_church(self, two):
        a, _b, _run_a, run_b = two
        for extra in ({"params": {"org_id": "200", "church": "200"}},
                      {"headers": {"X-Church-Id": "200", "X-Org-Id": "200"}}):
            assert a.get("/api/me", **extra).json()["church"]["name"] == "Liberty Baptist Church"
            assert a.get(f"/api/runs/{run_b}", **extra).status_code == 404


# ── Planning Center OAuth (against a stand-in; never run against the real thing) ──

class FakeHttp:
    def __init__(self, token_status=200):
        self.token_status, self.posts, self.gets = token_status, [], []

    class _R:
        def __init__(self, status, body):
            self.status_code, self._body = status, body

        def json(self):
            return self._body

    def post(self, url, data=None, timeout=None):
        self.posts.append((url, data))
        return self._R(self.token_status, {"access_token": "at-2", "refresh_token": "rt-2", "expires_in": 7200})

    def get(self, url, headers=None, timeout=None):
        self.gets.append((url, headers))
        if url.endswith("/people/v2"):
            return self._R(200, {"data": {"id": "4242", "attributes": {"name": "Test Church"}}})
        return self._R(200, {"data": {"id": "77", "attributes": {"name": "Pat Admin", "site_administrator": True}}})


class TestPcoOAuth:
    def test_exchange_sends_the_code_and_keeps_both_tokens(self):
        http = FakeHttp()
        token = pco_oauth.exchange_code("cid", "sec", "https://x.example", "the-code", http)
        assert token["access_token"] == "at-2" and token["refresh_token"] == "rt-2" and token["kind"] == "oauth"
        url, data = http.posts[0]
        assert url == pco_oauth.TOKEN_URL and data["code"] == "the-code"
        assert data["redirect_uri"] == "https://x.example/auth/pco/callback"

    def test_refused_token_request_raises(self):
        with pytest.raises(pco_oauth.OAuthError):
            pco_oauth.refresh("cid", "sec", "rt-1", FakeHttp(token_status=401))
        with pytest.raises(pco_oauth.OAuthError):
            pco_oauth.refresh("cid", "sec", "", FakeHttp())

    def test_who_am_i(self):
        who = pco_oauth.who_am_i("at", FakeHttp())
        assert who == {"org_id": "4242", "org_name": "Test Church", "person_id": "77",
                       "name": "Pat Admin", "admin": True}

    def test_a_failed_refresh_marks_the_church_for_reconnect(self, settings, store, monkeypatch):
        r = make_church(settings, store, "100", "Uno")
        r.save_secret("pco", {"kind": "oauth", "access_token": "old", "refresh_token": "rt"}, kind="oauth")

        def refuse(*_a, **_k):
            raise pco_oauth.OAuthError("revoked")
        monkeypatch.setattr(pco_oauth, "refresh", refuse)
        client = connections.pco_client(r, settings)
        with pytest.raises(pco_oauth.OAuthError):
            client.auth.refresh()
        assert r.church()["status"] == "needs_reconnect"

    def test_a_successful_refresh_is_saved_encrypted(self, settings, store, monkeypatch):
        r = make_church(settings, store, "100", "Uno")
        r.save_secret("pco", {"kind": "oauth", "access_token": "old", "refresh_token": "rt"}, kind="oauth")
        monkeypatch.setattr(pco_oauth, "refresh", lambda *_a, **_k: {
            "kind": "oauth", "access_token": "new-access", "refresh_token": "new-refresh", "expires_at": 1})
        client = connections.pco_client(r, settings)
        assert client.auth.refresh() is True
        assert client.auth.request_kwargs() == {"headers": {"Authorization": "Bearer new-access"}}
        assert r.secret("pco")["refresh_token"] == "new-refresh"
        assert "new-access" not in str(store.docs)


class TestStatsAndGuides:
    def test_a_run_reports_who_is_on_the_rosters(self, app):
        client = TestClient(app)
        client.post("/auth/dev/login", json={"church": "demo"}, headers=CSRF)
        run = client.get(f"/api/runs/{client.post('/api/runs', headers=CSRF).json()['id']}").json()
        assert run["totals"]["rosters"] == len(run["summary"]) == 6
        assert run["totals"]["active"] == sum(row["active"] for row in run["summary"]) > 0
        assert {row["report"] for row in run["summary"]} == {"sunday-school", "bus-routes"}
        assert client.get("/api/runs").json()["runs"][0]["totals"] == run["totals"]

    def test_instruction_guides_can_be_english_spanish_or_both(self, app):
        client = TestClient(app)
        client.post("/auth/dev/login", json={"church": "demo"}, headers=CSRF)

        def instructions_size():
            run = client.get(f"/api/runs/{client.post('/api/runs', headers=CSRF).json()['id']}").json()
            return next(o["bytes"] for o in run["outputs"] if o["path"].endswith("Instructions.pdf"))
        english_only = instructions_size()
        saved = client.put("/api/church", headers=CSRF, json={"instructions_languages": ["en", "es"]})
        assert saved.json()["instructions_languages"] == ["en", "es"]
        assert instructions_size() > english_only
        assert client.put("/api/church", headers=CSRF, json={"instructions_languages": []}).json()[
            "instructions_languages"] is None
        assert client.put("/api/church", headers=CSRF, json={"instructions_languages": ["fr"]}).status_code == 422


# ── Progress, cancel, schedule, preview ───────────────────────────────────────

from datetime import UTC, datetime  # noqa: E402

from advanced_reports import dispatch as scheduling  # noqa: E402


class TestProgressAndCancel:
    def test_outputs_say_which_report_and_class_they_belong_to(self, app):
        client = TestClient(app)
        client.post("/auth/dev/login", json={"church": "demo"}, headers=CSRF)
        run = client.get(f"/api/runs/{client.post('/api/runs', headers=CSRF).json()['id']}").json()
        by_kind = {}
        for out in run["outputs"]:
            by_kind.setdefault(out["kind"], []).append(out)
        assert len(by_kind["roster"]) == 6 and len(by_kind["volunteers"]) == 2 and len(by_kind["instructions"]) == 4
        nursery = next(o for o in by_kind["roster"] if o["location"] == "Nursery")
        assert nursery["report"] == "sunday-school" and nursery["path"] == "Sunday_School/Nursery/Roster.pdf"
        assert run["usage"]["steps"] > 20 and run["progress"] is None

    def test_second_run_knows_how_far_along_it_is(self, settings, store):
        r = make_church(settings, store, "100", "Uno")
        first = r.create_run("manual")
        runner.execute(settings, store, "100", first["id"])
        seen = []
        original = TenantRepo.save_run

        def spy(self, run):
            if run.get("progress"):
                seen.append(dict(run["progress"]))
            original(self, run)
        TenantRepo.save_run = spy
        try:
            second = r.create_run("manual")
            runner._SAVE_EVERY_S, keep = 0, runner._SAVE_EVERY_S
            runner.execute(settings, store, "100", second["id"])
        finally:
            TenantRepo.save_run = original
            runner._SAVE_EVERY_S = keep
        assert seen and all(0 < p["fraction"] <= 0.97 for p in seen)
        assert [p["fraction"] for p in seen] == sorted(p["fraction"] for p in seen)
        assert {p["phase"] for p in seen} >= {"event", "sundays", "checkins", "parents", "saving"}
        assert seen[-1]["report"]["label"] == "Bus Routes" and seen[-1]["report"]["count"] == 1

    def test_cancel_stops_the_run_and_keeps_no_files(self, settings, store):
        r = make_church(settings, store, "100", "Uno")
        run = r.create_run("manual")
        r.request_cancel(run["id"])
        assert runner.execute(settings, store, "100", run["id"]) is False
        done = r.run(run["id"])
        assert done["status"] == "cancelled" and done["outputs"] == [] and done["totals"] == {}
        assert not (settings.files_dir / "churches" / "100" / "runs" / run["id"]).exists()
        assert r.active_run() is None

    def test_cancel_route(self, settings, store):
        class Never:
            def launch(self, *_):
                pass
        make_church(settings, store, "100", "Uno")
        make_church(settings, store, "200", "Dos")
        app = create_app(settings, store, Never())
        a, b = client_for(app, settings, "100"), client_for(app, settings, "200")
        run_id = a.post("/api/runs", headers=CSRF).json()["id"]
        assert a.post(f"/api/runs/{run_id}/cancel").status_code == 403           # needs the CSRF header
        assert b.post(f"/api/runs/{run_id}/cancel", headers=CSRF).status_code == 404   # not their run
        assert a.get(f"/api/runs/{run_id}").json()["cancelling"] is False
        assert a.post(f"/api/runs/{run_id}/cancel", headers=CSRF).status_code == 200
        assert a.get(f"/api/runs/{run_id}").json()["cancelling"] is True
        runner.execute(settings, store, "100", run_id)
        assert a.get(f"/api/runs/{run_id}").json()["status"] == "cancelled"
        assert a.post(f"/api/runs/{run_id}/cancel", headers=CSRF).status_code == 409


class TestSchedule:
    SAT_6PM_CHICAGO = datetime(2026, 11, 15, 0, 5, tzinfo=UTC)      # Saturday 18:05 in America/Chicago

    def test_save_and_validate(self, app, settings, store):
        make_church(settings, store, "100", "Uno")
        client = client_for(app, settings, "100")
        assert client.get("/api/church").json()["schedule"] == {"enabled": False, "day": "sat", "time": "18:00"}
        saved = client.put("/api/church", headers=CSRF, json={"schedule": {"enabled": True, "day": "sun", "time": "05:30"}})
        assert saved.json()["schedule"] == {"enabled": True, "day": "sun", "time": "05:30"}
        for bad in ({"day": "someday", "time": "05:30"}, {"day": "sun", "time": "25:00"}, {"day": "sun"}):
            assert client.put("/api/church", headers=CSRF, json={"schedule": bad}).status_code == 422

    def test_due_only_on_its_day_and_hour_in_the_churchs_time_zone(self):
        church = {"timezone": "America/Chicago", "schedule": {"enabled": True, "day": "sat", "time": "18:00"}}
        assert scheduling.is_due(church, self.SAT_6PM_CHICAGO) == "2026-11-14"
        assert scheduling.is_due(church, datetime(2026, 11, 14, 23, 30, tzinfo=UTC)) is None      # 17:30, too early
        assert scheduling.is_due(church, datetime(2026, 11, 15, 4, 0, tzinfo=UTC)) is None        # 22:00, past the grace time
        assert scheduling.is_due({**church, "timezone": "Asia/Tokyo"}, self.SAT_6PM_CHICAGO) is None
        assert scheduling.is_due({**church, "schedule_last": "2026-11-14"}, self.SAT_6PM_CHICAGO) is None
        assert scheduling.is_due({**church, "schedule": {**church["schedule"], "enabled": False}}, self.SAT_6PM_CHICAGO) is None

    def test_dispatch_starts_each_due_church_once(self, settings, store, launcher):
        due, off = make_church(settings, store, "100", "Uno"), make_church(settings, store, "200", "Dos")
        due.update_church({"schedule": {"enabled": True, "day": "sat", "time": "18:00"}})
        off.update_church({"schedule": {"enabled": False, "day": "sat", "time": "18:00"}})
        assert scheduling.dispatch(settings, store, launcher, self.SAT_6PM_CHICAGO) == ["100"]
        assert scheduling.dispatch(settings, store, launcher, self.SAT_6PM_CHICAGO) == []
        (run,) = due.runs()
        assert run["trigger"] == "schedule" and run["status"] == "succeeded" and off.runs() == []

    def test_dispatch_route_needs_its_key(self, settings, store, launcher):
        assert TestClient(create_app(settings, store, launcher)).post("/internal/dispatch").status_code == 404
        keyed = Settings(data_dir=settings.data_dir, master_key_b64=settings.master_key_b64,
                         session_secret="s", dispatch_key="k3y")
        client = TestClient(create_app(keyed, store, launcher))
        assert client.post("/internal/dispatch", headers={"X-AR-Dispatch-Key": "wrong"}).status_code == 404
        assert client.post("/internal/dispatch", headers={"X-AR-Dispatch-Key": "k3y"}).json() == {"started": 0}


class TestPreviewAndColumns:
    def test_preview_follows_the_boxes_ticked(self, app, settings, store):
        from io import BytesIO

        from pypdf import PdfReader
        make_church(settings, store, "100", "Uno")
        client = client_for(app, settings, "100")

        def text(report):
            response = client.post("/api/preview/roster", headers=CSRF, json={"report": report})
            assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
            return "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
        full = text({"label": "Primarios"})
        slim = text({"label": "Primarios", "hide": ["phone", "address", "inactive"], "show_route": True})
        assert "Primarios" in full and "Teléfono" in full and "Ruta" not in full
        assert "Teléfono" not in slim and "Dirección" not in slim and "Ruta" in slim
        assert client.post("/api/preview/roster", headers=CSRF, json={"report": {"hide": ["shoes"]}}).status_code == 422
        assert TestClient(app).post("/api/preview/roster", headers=CSRF, json={"report": {}}).status_code == 401

    def test_saved_report_keeps_hidden_columns_and_a_run_uses_them(self, app, settings, store):
        make_church(settings, store, "100", "Uno")
        client = client_for(app, settings, "100")
        report = {**demo.REPORTS[1], "hide": ["address", "birthday"]}
        assert client.put("/api/modules/checkin_reports", headers=CSRF, json={"reports": [report]}).json()[
            "reports"][0]["hide"] == ["address", "birthday"]
        run = client.get(f"/api/runs/{client.post('/api/runs', headers=CSRF).json()['id']}").json()
        assert run["status"] == "succeeded"
