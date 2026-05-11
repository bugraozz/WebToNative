from __future__ import annotations

import json
import time
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR.parent / ".data"
JOBS_DIR = DATA_DIR / "jobs"


def _ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def create_job() -> str:
    _ensure_dirs()
    job_id = uuid.uuid4().hex
    (JOBS_DIR / job_id).mkdir(parents=True, exist_ok=True)
    return job_id


def job_exists(job_id: str) -> bool:
    return (JOBS_DIR / job_id).exists()


def get_job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def _status_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "status.json"


def save_upload(job_id: str, upload: UploadFile) -> Path:
    job_dir = get_job_dir(job_id)
    dest = job_dir / "input.zip"
    with dest.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    return dest


def save_repo_url(job_id: str, repo_url: str) -> Path:
    job_dir = get_job_dir(job_id)
    dest = job_dir / "repo.txt"
    dest.write_text(repo_url.strip(), encoding="utf-8")
    return dest


def init_status(
    job_id: str,
    state: str,
    step: str,
    progress: int,
    error: str | None = None,
) -> Path:
    payload = {
        "state": state,
        "step": step,
        "progress": progress,
        "error": error,
        "started_at": time.time(),
        "updated_at": time.time(),
    }
    path = _status_path(job_id)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def update_status(
    job_id: str,
    state: str | None = None,
    step: str | None = None,
    progress: int | None = None,
    error: str | None = None,
) -> Path:
    path = _status_path(job_id)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {
            "state": "queued",
            "step": "Queued",
            "progress": 0,
            "started_at": time.time(),
        }

    if state is not None:
        payload["state"] = state
    if step is not None:
        payload["step"] = step
    if progress is not None:
        payload["progress"] = progress
    if error is not None:
        payload["error"] = error

    payload["updated_at"] = time.time()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_status(job_id: str) -> dict[str, Any] | None:
    path = _status_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def extract_zip(job_id: str) -> Path:
    job_dir = get_job_dir(job_id)
    source_dir = job_dir / "source"
    if source_dir.exists():
        return source_dir

    input_zip = job_dir / "input.zip"
    source_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(input_zip, "r") as archive:
        archive.extractall(source_dir)

    return source_dir


def clone_repo(job_id: str) -> Path:
    job_dir = get_job_dir(job_id)
    source_dir = job_dir / "source"
    if source_dir.exists():
        return source_dir

    repo_url_path = job_dir / "repo.txt"
    repo_url = repo_url_path.read_text(encoding="utf-8").strip()
    source_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(source_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Git clone failed"
        raise RuntimeError(message)

    return source_dir


def get_source_dir(job_id: str) -> Path:
    job_dir = get_job_dir(job_id)
    source_dir = job_dir / "source"
    if source_dir.exists():
        return source_dir

    if (job_dir / "input.zip").exists():
        return extract_zip(job_id)
    if (job_dir / "repo.txt").exists():
        return clone_repo(job_id)

    raise FileNotFoundError("No input for job")


def get_output_dir(job_id: str) -> Path:
    job_dir = get_job_dir(job_id)
    output_dir = job_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_metadata(job_id: str, metadata: dict[str, Any]) -> Path:
    job_dir = get_job_dir(job_id)
    path = job_dir / "meta.json"
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return path


def save_analysis(job_id: str, detected: dict[str, Any]) -> Path:
    job_dir = get_job_dir(job_id)
    path = job_dir / "analysis.json"
    path.write_text(json.dumps(detected, indent=2), encoding="utf-8")
    return path


def load_analysis(job_id: str) -> dict[str, Any] | None:
    path = get_job_dir(job_id) / "analysis.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_report(job_id: str, report: Any) -> Path:
    job_dir = get_job_dir(job_id)
    path = job_dir / "report.json"

    if hasattr(report, "model_dump"):
        payload = report.model_dump()
    elif hasattr(report, "dict"):
        payload = report.dict()
    else:
        payload = report

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_report(job_id: str) -> Any | None:
    job_dir = get_job_dir(job_id)
    path = job_dir / "report.json"
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def make_output_zip(job_id: str) -> Path:
    job_dir = get_job_dir(job_id)
    output_root = job_dir / "output" / "react-native"
    zip_path = job_dir / "output.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        if output_root.exists():
            for path in output_root.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(output_root))

    return zip_path


def get_output_zip_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "output.zip"
