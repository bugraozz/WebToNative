import time

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .models import (
    AnalyzeResponse,
    AnalyzeStartResponse,
    ConvertRequest,
    ConvertResponse,
    DetectedSummary,
    Report,
    StatusResponse,
)
from .services import analyzer, converter, report as report_service, storage

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeStartResponse)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(default=None),
    repo_url: str | None = Form(default=None),
) -> AnalyzeStartResponse:
    if file is None and not repo_url:
        raise HTTPException(status_code=400, detail="Provide a zip file or repo_url")

    job_id = storage.create_job()
    storage.init_status(job_id, state="queued", step="Queued", progress=0)

    if file is not None:
        storage.save_upload(job_id, file)
        storage.update_status(job_id, state="uploaded", step="Upload complete", progress=10)
        background_tasks.add_task(_process_zip_job, job_id)
    else:
        storage.save_repo_url(job_id, repo_url or "")
        storage.update_status(job_id, state="queued", step="Repo queued", progress=5)
        background_tasks.add_task(_process_repo_job, job_id, repo_url or "")

    return AnalyzeStartResponse(job_id=job_id, status=_build_status_response(job_id))


@router.post("/convert", response_model=ConvertResponse)
def convert(req: ConvertRequest) -> ConvertResponse:
    if not storage.job_exists(req.job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    source_dir = storage.get_source_dir(req.job_id)
    output_dir = storage.get_output_dir(req.job_id)

    result = converter.convert_project(source_dir, output_dir, req.selection)
    report = report_service.build_report(result)

    storage.save_report(req.job_id, report)
    storage.make_output_zip(req.job_id)

    return ConvertResponse(
        job_id=req.job_id,
        report=report,
        download_url=f"/api/download/{req.job_id}",
    )


@router.get("/report/{job_id}", response_model=Report)
def get_report(job_id: str) -> Report:
    report_data = storage.load_report(job_id)
    if report_data is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return Report(**report_data)


@router.get("/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str) -> StatusResponse:
    return _build_status_response(job_id)


@router.get("/analysis/{job_id}", response_model=AnalyzeResponse)
def get_analysis(job_id: str) -> AnalyzeResponse:
    analysis_data = storage.load_analysis(job_id)
    if analysis_data is None:
        raise HTTPException(status_code=404, detail="Analysis not ready")
    return AnalyzeResponse(job_id=job_id, detected=DetectedSummary(**analysis_data))


@router.get("/download/{job_id}")
def download(job_id: str) -> FileResponse:
    zip_path = storage.get_output_zip_path(job_id)
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Output zip not found")
    return FileResponse(
        path=zip_path,
        filename=f"{job_id}-react-native.zip",
        media_type="application/zip",
    )


def _process_zip_job(job_id: str) -> None:
    try:
        storage.update_status(job_id, state="extracting", step="Extracting files", progress=20)
        source_dir = storage.extract_zip(job_id)
        storage.update_status(job_id, state="analyzing", step="Analyzing project", progress=65)
        detected = analyzer.analyze_project(source_dir)
        detected_payload = (
            detected.model_dump() if hasattr(detected, "model_dump") else detected.dict()
        )
        storage.save_analysis(job_id, detected_payload)
        storage.save_metadata(job_id, {"input_type": "zip", "detected": detected_payload})
        storage.update_status(job_id, state="done", step="Completed", progress=100)
    except Exception as exc:  # pragma: no cover
        storage.save_metadata(job_id, {"error": str(exc)})
        storage.update_status(job_id, state="error", step="Error", progress=100, error=str(exc))


def _process_repo_job(job_id: str, repo_url: str) -> None:
    try:
        storage.update_status(job_id, state="cloning", step="Cloning repository", progress=20)
        source_dir = storage.clone_repo(job_id)
        storage.update_status(job_id, state="analyzing", step="Analyzing project", progress=65)
        detected = analyzer.analyze_project(source_dir)
        detected_payload = (
            detected.model_dump() if hasattr(detected, "model_dump") else detected.dict()
        )
        storage.save_analysis(job_id, detected_payload)
        storage.save_metadata(
            job_id,
            {"input_type": "git", "repo_url": repo_url, "detected": detected_payload},
        )
        storage.update_status(job_id, state="done", step="Completed", progress=100)
    except Exception as exc:  # pragma: no cover
        storage.save_metadata(job_id, {"error": str(exc)})
        storage.update_status(job_id, state="error", step="Error", progress=100, error=str(exc))


def _build_status_response(job_id: str) -> StatusResponse:
    status = storage.load_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Status not found")

    progress = int(status.get("progress", 0) or 0)
    eta_seconds = None
    started_at = status.get("started_at")
    if isinstance(started_at, (int, float)) and 0 < progress < 100:
        elapsed = max(0.0, time.time() - started_at)
        if progress > 0:
            eta_seconds = int((elapsed * (100 - progress)) / progress)

    return StatusResponse(
        job_id=job_id,
        state=status.get("state", "unknown"),
        step=status.get("step", "Working"),
        progress=progress,
        eta_seconds=eta_seconds,
        error=status.get("error"),
    )
