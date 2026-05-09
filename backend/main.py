
import io
import json
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel

from backend.pipeline import run_pipeline
from backend.schemas import AuditResponse
from backend.engine.report import stream_report

from pathlib import Path

app = FastAPI(
    title="AI Data Quality Auditor",
    description="Upload a CSV and receive a full data quality audit with AI-generated report.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)



BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


@app.post("/audit", response_model=AuditResponse)
async def audit(
    file: UploadFile = File(..., description="CSV file to audit"),
    rules: str = Form(default="{}", description="JSON-encoded validation rules"),
    generate_report: bool = Form(default=False, description="Generate AI report (use /audit/report/stream instead)"),
):
    """
    Full audit pipeline: CSV → ingestion → profiling → validation → anomaly → aggregation → scoring
    
    Returns complete audit result WITHOUT AI report.
    Use POST /audit/report/stream for streaming report generation.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    try:
        user_rules = json.loads(rules)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in rules field.")

    content = await file.read()

    try:
        result = run_pipeline(
            filename=file.filename,
            content=content,
            user_rules=user_rules,
            generate_report_flag=False, 
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")

    return result


class StreamReportRequest(BaseModel):
    """Request payload for streaming report generation."""
    filename: str
    profile: list[dict]
    issues: list[dict]
    anomalies: dict
    score: dict
    drift: Optional[dict] = None


@app.post("/audit/report/stream")
async def stream_audit_report(request: StreamReportRequest):
    """
    Stream an AI-generated report using Server-Sent Events (SSE).
    
    Call this AFTER /audit with the audit results.
    
    Frontend: Use EventSource or fetch with ReadableStream to consume chunks.
    Each chunk is JSON: {"chunk": "text fragment"}
    
    Example frontend:
        const eventSource = new EventSource('/audit/report/stream');
        eventSource.onmessage = (event) => {
            const {chunk} = JSON.parse(event.data);
            appendToReport(chunk);
        };
    """
    try:
        def generate():
            for sse_chunk in stream_report(
                filename=request.filename,
                profile=request.profile,
                issues=request.issues,
                anomalies=request.anomalies,
                score=request.score,
                drift=request.drift,
            ):
                yield sse_chunk

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report streaming failed: {str(e)}")