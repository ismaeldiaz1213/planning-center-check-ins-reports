# tests/test_api.py
#
# Integration tests for the FastAPI server (api.py).
# Uses TestClient (no real network or subprocess calls).
# All file-system and subprocess interactions are mocked.

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
from api import _jobs, _jobs_lock, app, _read_dotenv, _write_dotenv

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_job(job_id: str, job_type: str = "rutas", status: str = "success", output: list[str] | None = None):
    """Inject a synthetic job directly into the in-memory store."""
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": status,
            "output": output or [],
            "started_at": "2026-01-01T10:00:00+00:00",
            "finished_at": "2026-01-01T10:00:30+00:00" if status != "running" else None,
        }


def _clear_jobs():
    with _jobs_lock:
        _jobs.clear()


# ── /api/health ───────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_ok(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ── /api/previews ─────────────────────────────────────────────────────────────

class TestListPreviews:
    def test_returns_empty_list_when_no_pdfs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(api, "PREVIEWS_DIR", tmp_path)
        resp = client.get("/api/previews")
        assert resp.status_code == 200
        assert resp.json() == {"previews": []}

    def test_returns_metadata_for_roster_pdf(self, tmp_path, monkeypatch):
        (tmp_path / "default_Roster.pdf").write_bytes(b"%PDF-1.4 placeholder")
        monkeypatch.setattr(api, "PREVIEWS_DIR", tmp_path)
        resp = client.get("/api/previews")
        assert resp.status_code == 200
        previews = resp.json()["previews"]
        assert len(previews) == 1
        p = previews[0]
        assert p["filename"] == "default_Roster.pdf"
        assert p["theme"] == "default"
        assert p["type"] == "roster"
        assert p["url"] == "/previews/default_Roster.pdf"

    def test_returns_metadata_for_seasonal_pdf(self, tmp_path, monkeypatch):
        (tmp_path / "primavera_Escuela-Roster.pdf").write_bytes(b"%PDF")
        monkeypatch.setattr(api, "PREVIEWS_DIR", tmp_path)
        resp = client.get("/api/previews")
        previews = resp.json()["previews"]
        assert previews[0]["theme"] == "primavera"
        assert previews[0]["type"] == "escuela"

    def test_returns_metadata_for_direcciones_pdf(self, tmp_path, monkeypatch):
        (tmp_path / "verano_Direcciones-Roster.pdf").write_bytes(b"%PDF")
        monkeypatch.setattr(api, "PREVIEWS_DIR", tmp_path)
        resp = client.get("/api/previews")
        previews = resp.json()["previews"]
        assert previews[0]["theme"] == "verano"
        assert previews[0]["type"] == "direcciones"

    def test_returns_multiple_pdfs_sorted(self, tmp_path, monkeypatch):
        (tmp_path / "default_Roster.pdf").write_bytes(b"%PDF")
        (tmp_path / "primavera_Roster.pdf").write_bytes(b"%PDF")
        monkeypatch.setattr(api, "PREVIEWS_DIR", tmp_path)
        resp = client.get("/api/previews")
        filenames = [p["filename"] for p in resp.json()["previews"]]
        assert filenames == sorted(filenames)


# ── /api/previews/generate ────────────────────────────────────────────────────

class TestGeneratePreview:
    def setup_method(self):
        _clear_jobs()

    @patch("api._run_subprocess")
    def test_returns_job_id(self, mock_run):
        resp = client.post("/api/previews/generate", json={})
        assert resp.status_code == 202
        assert "job_id" in resp.json()

    @patch("api._run_subprocess")
    def test_passes_type_all_when_no_type_given(self, mock_run):
        client.post("/api/previews/generate", json={})
        cmd = mock_run.call_args[0][1]
        assert "--type" in cmd
        assert "all" in cmd

    @patch("api._run_subprocess")
    def test_passes_specific_type(self, mock_run):
        client.post("/api/previews/generate", json={"type": "escuela"})
        cmd = mock_run.call_args[0][1]
        assert cmd[cmd.index("--type") + 1] == "escuela"

    @patch("api._run_subprocess")
    def test_passes_theme_when_provided(self, mock_run):
        client.post("/api/previews/generate", json={"theme": "primavera", "type": "roster"})
        cmd = mock_run.call_args[0][1]
        assert "--theme" in cmd
        assert "primavera" in cmd

    @patch("api._run_subprocess")
    def test_does_not_pass_theme_when_default(self, mock_run):
        client.post("/api/previews/generate", json={"theme": "default"})
        cmd = mock_run.call_args[0][1]
        assert "--theme" not in cmd


# ── /api/jobs ─────────────────────────────────────────────────────────────────

class TestListJobs:
    def setup_method(self):
        _clear_jobs()

    def test_returns_empty_list_when_no_jobs(self):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json() == {"jobs": []}

    def test_returns_all_jobs(self):
        _make_job("j1", "rutas")
        _make_job("j2", "escuela")
        resp = client.get("/api/jobs")
        jobs = resp.json()["jobs"]
        assert len(jobs) == 2

    def test_jobs_sorted_newest_first(self):
        _make_job("j-old", "rutas")
        # Override started_at to make ordering unambiguous
        with _jobs_lock:
            _jobs["j-old"]["started_at"] = "2026-01-01T09:00:00+00:00"
        _make_job("j-new", "escuela")
        with _jobs_lock:
            _jobs["j-new"]["started_at"] = "2026-01-01T10:00:00+00:00"

        resp = client.get("/api/jobs")
        ids = [j["id"] for j in resp.json()["jobs"]]
        assert ids[0] == "j-new"
        assert ids[1] == "j-old"


# ── /api/jobs/{job_id} ────────────────────────────────────────────────────────

class TestGetJob:
    def setup_method(self):
        _clear_jobs()

    def test_returns_job_details(self):
        _make_job("job-abc", "rutas", "success", ["line1", "line2"])
        resp = client.get("/api/jobs/job-abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "job-abc"
        assert data["type"] == "rutas"
        assert data["status"] == "success"
        assert data["output"] == ["line1", "line2"]
        assert data["total_lines"] == 2

    def test_returns_404_for_unknown_job(self):
        resp = client.get("/api/jobs/nonexistent")
        assert resp.status_code == 404

    def test_since_parameter_slices_output(self):
        _make_job("job-xyz", output=["a", "b", "c", "d"])
        resp = client.get("/api/jobs/job-xyz?since=2")
        assert resp.json()["output"] == ["c", "d"]

    def test_since_zero_returns_all_output(self):
        _make_job("job-xyz", output=["a", "b"])
        resp = client.get("/api/jobs/job-xyz?since=0")
        assert resp.json()["output"] == ["a", "b"]


# ── /api/jobs/rutas/run ───────────────────────────────────────────────────────

class TestRunRutas:
    def setup_method(self):
        _clear_jobs()

    @patch("api._run_subprocess")
    def test_returns_202_with_job_id(self, mock_run):
        resp = client.post("/api/jobs/rutas/run")
        assert resp.status_code == 202
        assert "job_id" in resp.json()

    @patch("api._run_subprocess")
    def test_command_includes_rutas_and_weeks(self, mock_run, monkeypatch):
        monkeypatch.delenv("RUTAS_DEFAULT_WEEKS", raising=False)
        monkeypatch.delenv("RUTAS_DEFAULT_THEME", raising=False)
        client.post("/api/jobs/rutas/run")
        cmd = mock_run.call_args[0][1]
        assert "Rutas" in cmd
        assert "--weeks" in cmd
        assert "5" in cmd  # default weeks

    @patch("api._run_subprocess")
    def test_command_uses_env_default_weeks(self, mock_run, monkeypatch):
        monkeypatch.setenv("RUTAS_DEFAULT_WEEKS", "8")
        monkeypatch.delenv("RUTAS_DEFAULT_THEME", raising=False)
        client.post("/api/jobs/rutas/run")
        cmd = mock_run.call_args[0][1]
        assert cmd[cmd.index("--weeks") + 1] == "8"

    @patch("api._run_subprocess")
    def test_command_uses_env_default_theme(self, mock_run, monkeypatch):
        monkeypatch.setenv("RUTAS_DEFAULT_THEME", "primavera")
        monkeypatch.setenv("RUTAS_DEFAULT_WEEKS", "5")
        client.post("/api/jobs/rutas/run")
        cmd = mock_run.call_args[0][1]
        assert "--theme" in cmd
        assert "primavera" in cmd

    @patch("api._run_subprocess")
    def test_command_omits_theme_when_blank(self, mock_run, monkeypatch):
        monkeypatch.setenv("RUTAS_DEFAULT_THEME", "")
        client.post("/api/jobs/rutas/run")
        cmd = mock_run.call_args[0][1]
        assert "--theme" not in cmd

    @patch("api._run_subprocess")
    def test_job_type_is_rutas(self, mock_run):
        resp = client.post("/api/jobs/rutas/run")
        job_id = resp.json()["job_id"]
        with _jobs_lock:
            assert _jobs[job_id]["type"] == "rutas"


# ── /api/jobs/escuela/run ─────────────────────────────────────────────────────

class TestRunEscuela:
    def setup_method(self):
        _clear_jobs()

    @patch("api._run_subprocess")
    def test_returns_202_with_job_id(self, mock_run):
        resp = client.post("/api/jobs/escuela/run")
        assert resp.status_code == 202
        assert "job_id" in resp.json()

    @patch("api._run_subprocess")
    def test_command_includes_escuela_dominical(self, mock_run, monkeypatch):
        monkeypatch.delenv("ESCUELA_DEFAULT_WEEKS", raising=False)
        monkeypatch.delenv("ESCUELA_DEFAULT_THEME", raising=False)
        client.post("/api/jobs/escuela/run")
        cmd = mock_run.call_args[0][1]
        assert "Escuela Dominical" in cmd

    @patch("api._run_subprocess")
    def test_command_uses_env_default_weeks(self, mock_run, monkeypatch):
        monkeypatch.setenv("ESCUELA_DEFAULT_WEEKS", "3")
        monkeypatch.delenv("ESCUELA_DEFAULT_THEME", raising=False)
        client.post("/api/jobs/escuela/run")
        cmd = mock_run.call_args[0][1]
        assert cmd[cmd.index("--weeks") + 1] == "3"

    @patch("api._run_subprocess")
    def test_job_type_is_escuela(self, mock_run):
        resp = client.post("/api/jobs/escuela/run")
        job_id = resp.json()["job_id"]
        with _jobs_lock:
            assert _jobs[job_id]["type"] == "escuela"


# ── /api/settings GET ─────────────────────────────────────────────────────────

class TestGetSettings:
    def test_returns_200(self, monkeypatch):
        monkeypatch.setenv("PCO_APP_ID", "test-app-id")
        monkeypatch.setenv("PCO_SECRET", "test-secret")
        monkeypatch.setenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "test-folder")
        monkeypatch.delenv("RUTAS_DEFAULT_WEEKS", raising=False)
        monkeypatch.delenv("ESCUELA_DEFAULT_WEEKS", raising=False)
        resp = client.get("/api/settings")
        assert resp.status_code == 200

    def test_returns_expected_keys(self, monkeypatch):
        monkeypatch.setenv("PCO_APP_ID", "app-123")
        monkeypatch.setenv("PCO_SECRET", "sec-456")
        monkeypatch.setenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "folder-789")
        monkeypatch.delenv("RUTAS_DEFAULT_WEEKS", raising=False)
        monkeypatch.delenv("ESCUELA_DEFAULT_WEEKS", raising=False)
        monkeypatch.delenv("RUTAS_DEFAULT_THEME", raising=False)
        monkeypatch.delenv("ESCUELA_DEFAULT_THEME", raising=False)
        resp = client.get("/api/settings")
        data = resp.json()
        assert data["pco_app_id"] == "app-123"
        assert data["pco_secret"] == "sec-456"
        assert data["google_drive_parent_folder_id"] == "folder-789"

    def test_defaults_weeks_to_5_when_unset(self, monkeypatch):
        monkeypatch.delenv("RUTAS_DEFAULT_WEEKS", raising=False)
        monkeypatch.delenv("ESCUELA_DEFAULT_WEEKS", raising=False)
        resp = client.get("/api/settings")
        data = resp.json()
        assert data["rutas_weeks"] == 5
        assert data["escuela_weeks"] == 5

    def test_reads_custom_weeks_from_env(self, monkeypatch):
        monkeypatch.setenv("RUTAS_DEFAULT_WEEKS", "7")
        monkeypatch.setenv("ESCUELA_DEFAULT_WEEKS", "3")
        resp = client.get("/api/settings")
        data = resp.json()
        assert data["rutas_weeks"] == 7
        assert data["escuela_weeks"] == 3


# ── /api/settings PUT ─────────────────────────────────────────────────────────

class TestUpdateSettings:
    @patch("api._write_dotenv")
    def test_returns_ok(self, mock_write):
        resp = client.put("/api/settings", json={"pco_app_id": "new-id"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    @patch("api._write_dotenv")
    def test_maps_field_to_env_key(self, mock_write):
        client.put("/api/settings", json={"pco_app_id": "NEW_ID"})
        updates = mock_write.call_args[0][0]
        assert updates["PCO_APP_ID"] == "NEW_ID"

    @patch("api._write_dotenv")
    def test_maps_pco_secret(self, mock_write):
        client.put("/api/settings", json={"pco_secret": "new-secret"})
        updates = mock_write.call_args[0][0]
        assert updates["PCO_SECRET"] == "new-secret"

    @patch("api._write_dotenv")
    def test_maps_drive_folder_id(self, mock_write):
        client.put("/api/settings", json={"google_drive_parent_folder_id": "new-folder"})
        updates = mock_write.call_args[0][0]
        assert updates["GOOGLE_DRIVE_PARENT_FOLDER_ID"] == "new-folder"

    @patch("api._write_dotenv")
    def test_maps_rutas_weeks(self, mock_write):
        client.put("/api/settings", json={"rutas_weeks": 10})
        updates = mock_write.call_args[0][0]
        assert updates["RUTAS_DEFAULT_WEEKS"] == "10"

    @patch("api._write_dotenv")
    def test_rejects_invalid_theme(self, mock_write):
        client.put("/api/settings", json={"rutas_theme": "invalid-theme"})
        updates = mock_write.call_args[0][0]
        assert updates["RUTAS_DEFAULT_THEME"] == ""

    @patch("api._write_dotenv")
    def test_accepts_valid_theme(self, mock_write):
        for theme in ("primavera", "verano", "otono", "invierno"):
            client.put("/api/settings", json={"rutas_theme": theme})
            updates = mock_write.call_args[0][0]
            assert updates["RUTAS_DEFAULT_THEME"] == theme

    @patch("api._write_dotenv")
    def test_empty_body_does_not_call_write(self, mock_write):
        client.put("/api/settings", json={})
        mock_write.assert_not_called()


# ── .env helpers (_read_dotenv / _write_dotenv) ────────────────────────────────

class TestDotenvHelpers:
    def test_read_returns_empty_dict_for_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(api, "ENV_PATH", tmp_path / ".env")
        result = _read_dotenv()
        assert result == {}

    def test_read_parses_simple_key_value(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        monkeypatch.setattr(api, "ENV_PATH", env_file)
        result = _read_dotenv()
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_read_ignores_comments_and_blank_lines(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("# a comment\n\nFOO=bar\n")
        monkeypatch.setattr(api, "ENV_PATH", env_file)
        result = _read_dotenv()
        assert result == {"FOO": "bar"}

    def test_write_creates_new_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        monkeypatch.setattr(api, "ENV_PATH", env_file)
        _write_dotenv({"FOO": "newval"})
        assert "FOO=newval" in env_file.read_text()

    def test_write_updates_existing_key(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=old\nBAR=keep\n")
        monkeypatch.setattr(api, "ENV_PATH", env_file)
        _write_dotenv({"FOO": "new"})
        content = env_file.read_text()
        assert "FOO=new" in content
        assert "FOO=old" not in content
        assert "BAR=keep" in content

    def test_write_appends_new_key(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=val\n")
        monkeypatch.setattr(api, "ENV_PATH", env_file)
        _write_dotenv({"NEW_KEY": "newval"})
        content = env_file.read_text()
        assert "EXISTING=val" in content
        assert "NEW_KEY=newval" in content

    def test_write_updates_os_environ(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        monkeypatch.setattr(api, "ENV_PATH", env_file)
        _write_dotenv({"TEST_ENV_VAR": "hello"})
        assert os.environ.get("TEST_ENV_VAR") == "hello"
        del os.environ["TEST_ENV_VAR"]
