"""
Demo router — a public, self-contained example of the async job flow.

Exposes POST /demo/job which submits the sample "summarize a topic" job into
the existing SQLite job queue. The job then flows through the standard
/jobs and /jobs/{job_id} endpoints just like any real async job.

This router is API-key protected (wired up in main.py via verify_api_key) and
depends only on the bundled demo.sample_job module — no private routers,
adapters, clients_config, or .env required.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from gateway.jobs import job_queue
from gateway.models import AsyncJobResponse
from gateway.demo.sample_job import summarize_topic

router = APIRouter()


class DemoJobRequest(BaseModel):
    """Request body for the demo job."""

    topic: str = Field(
        "how to answer the phone after hours",
        description="Topic for the sample 'summarize a topic' job (demo data).",
        max_length=500,
    )
    duration_seconds: int = Field(
        3,
        ge=0,
        le=10,
        description="How long the mock job should 'work' before returning.",
    )


@router.post("/job", response_model=AsyncJobResponse)
async def submit_demo_job(request: DemoJobRequest):
    """
    Submit the sample async job into the shared job queue.

    Returns a job_id immediately. Poll GET /jobs and GET /jobs/{job_id} to
    watch it move pending -> running -> completed and read the fake summary.
    """
    job_id = job_queue.create_job(
        command="demo_summarize_topic",
        client="demo",
        options={"topic": request.topic, "duration_seconds": request.duration_seconds},
    )

    job_queue.submit_job(
        job_id,
        summarize_topic,
        topic=request.topic,
        duration_seconds=request.duration_seconds,
    )

    return AsyncJobResponse(
        job_id=job_id,
        status="pending",
        message="Demo summarize-topic job queued",
    )
