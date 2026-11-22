# advanced_reports/core/cloud_run.py
#
# Starting a run on Google Cloud: one Cloud Run job execution per run, with the
# church id and run id as its arguments (plan §3.1, §3.7 rule 3). Locally the
# web service starts the runner as a subprocess instead (app.SubprocessLauncher).
#
# The job's container runs `python -m advanced_reports.runner`; the execution's
# arguments are <org_id> <run_id>. The web service's service account needs
# run.jobs.runWithOverrides on the job (deploy/platform.sh grants it).

from __future__ import annotations

import google.auth
from google.auth.transport.requests import AuthorizedSession

_API = "https://run.googleapis.com/v2"


class CloudRunJobLauncher:
    def __init__(self, job: str, session=None):
        """`job` is the full name: projects/<p>/locations/<region>/jobs/<name>."""
        if not job.startswith("projects/") or "/jobs/" not in job:
            raise ValueError(f"AR_RUNNER_JOB must be projects/<p>/locations/<r>/jobs/<name>, got {job!r}")
        self.job = job
        self._session = session

    def _http(self):
        if self._session is None:
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            self._session = AuthorizedSession(credentials)
        return self._session

    def launch(self, org_id: str, run_id: str) -> None:
        body = {"overrides": {"containerOverrides": [{"args": [org_id, run_id]}], "taskCount": 1}}
        response = self._http().post(f"{_API}/{self.job}:run", json=body, timeout=30)
        if response.status_code >= 300:
            raise RuntimeError(f"Cloud Run refused to start the run ({response.status_code}): {response.text[:300]}")
