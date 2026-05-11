from typing import List, Optional

from pydantic import BaseModel, Field


class DetectedSummary(BaseModel):
    frontend: List[str] = Field(default_factory=list)
    backend: List[str] = Field(default_factory=list)
    database: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    payments: List[str] = Field(default_factory=list)
    docker: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    job_id: str
    detected: DetectedSummary


class StatusResponse(BaseModel):
    job_id: str
    state: str
    step: str
    progress: int
    eta_seconds: Optional[int] = None
    error: Optional[str] = None


class AnalyzeStartResponse(BaseModel):
    job_id: str
    status: StatusResponse


class Selection(BaseModel):
    frontend: Optional[str] = None
    backend: Optional[str] = None
    database: Optional[str] = None
    styles: Optional[str] = None


class ConvertRequest(BaseModel):
    job_id: str
    selection: Selection


class Report(BaseModel):
    score: float
    success_rate: float
    files_total: int
    files_converted: int
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ConvertResponse(BaseModel):
    job_id: str
    report: Report
    download_url: str
