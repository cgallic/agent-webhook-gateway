"""
MiKai Intelligence — audit intake + lead management router.

Public endpoints (no API key):
  POST /api/mikai/audit — submit audit request from landing page form

Authenticated endpoints:
  GET  /api/mikai/leads — list all leads
  GET  /api/mikai/leads/{domain} — get lead + audit status
  POST /api/mikai/run/{domain} — manually trigger audit for a lead
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from gateway.auth import verify_api_key
from gateway.models import WebhookResponse

LOOPS_API_KEY = os.environ.get("LOOPS_API_KEY_CONNORGALLIC", "")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "mikai"
LEADS_FILE = DATA_DIR / "leads.json"
AUDITS_DIR = DATA_DIR / "audits"

# Ensure dirs exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDITS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AuditRequest(BaseModel):
    """Public audit form submission."""
    domain: str = Field(..., description="Domain to audit (e.g. example.com)")
    email: str = Field(..., description="Email to send report to")
    name: str = Field(..., description="Contact name")


class Lead(BaseModel):
    """Internal lead record."""
    domain: str
    email: str
    name: str
    submitted_at: str
    status: str = "pending"  # pending | running | sent | failed
    audit_path: Optional[str] = None
    score: Optional[int] = None
    gaps_count: Optional[int] = None
    tasks_total: Optional[int] = None
    sent_at: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Lead persistence (JSON file — simple, works for <1000 leads)
# ---------------------------------------------------------------------------

def _load_leads() -> list[dict]:
    if LEADS_FILE.exists():
        return json.loads(LEADS_FILE.read_text(encoding="utf-8"))
    return []


def _save_leads(leads: list[dict]):
    LEADS_FILE.write_text(json.dumps(leads, indent=2, default=str), encoding="utf-8")


def _find_lead(domain: str) -> Optional[dict]:
    for lead in _load_leads():
        if lead["domain"] == domain:
            return lead
    return None


def _clean_domain(raw: str) -> str:
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split("?")[0]
    return d


# ---------------------------------------------------------------------------
# Background audit runner
# ---------------------------------------------------------------------------

def _run_audit_background(domain: str):
    """Run audit in background and update lead status."""
    leads = _load_leads()
    lead = None
    for l in leads:
        if l["domain"] == domain:
            lead = l
            break

    if not lead:
        return

    lead["status"] = "running"
    _save_leads(leads)

    try:
        # Run the audit script
        audit_md = AUDITS_DIR / f"{domain}.md"
        audit_json = AUDITS_DIR / f"{domain}.json"

        project_root = Path(__file__).parent.parent.parent

        # Generate markdown report
        result = subprocess.run(
            [sys.executable, "-m", "scripts.mikai.audit", domain, "--output", str(audit_md)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            lead["status"] = "failed"
            lead["error"] = result.stderr[:500]
            _save_leads(leads)
            return

        # Also generate JSON for data extraction
        result_json = subprocess.run(
            [sys.executable, "-m", "scripts.mikai.audit", domain, "--json", "--output", str(audit_json)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Extract summary from JSON
        if audit_json.exists():
            data = json.loads(audit_json.read_text(encoding="utf-8"))
            lead["score"] = data.get("scores", {}).get("overall", 0)
            lead["gaps_count"] = len(data.get("gaps", []))
            lead["tasks_total"] = data.get("pricing_summary", {}).get("all_tasks_total", 0)

        lead["audit_path"] = str(audit_md)

        # Send via Loops
        email_sent = _send_via_loops(
            email=lead["email"],
            name=lead["name"],
            domain=domain,
            score=lead.get("score", 0),
            gaps_count=lead.get("gaps_count", 0),
            tasks_total=lead.get("tasks_total", 0),
            report_url=f"https://meetkai.xyz/reports/{domain}",
        )

        lead["status"] = "sent" if email_sent else "failed"
        if not email_sent:
            lead["error"] = "Loops email delivery failed"
        lead["sent_at"] = datetime.now(timezone.utc).isoformat()
        _save_leads(leads)

    except subprocess.TimeoutExpired:
        lead["status"] = "failed"
        lead["error"] = "Audit timed out after 120s"
        _save_leads(leads)
    except Exception as e:
        lead["status"] = "failed"
        lead["error"] = str(e)[:500]
        _save_leads(leads)


# ---------------------------------------------------------------------------
# Loops email delivery
# ---------------------------------------------------------------------------

def _send_via_loops(
    email: str,
    name: str,
    domain: str,
    score: int,
    gaps_count: int,
    tasks_total: int,
    report_url: str,
) -> bool:
    """Send audit report notification via Loops transactional or event API."""
    if not LOOPS_API_KEY:
        print("[MiKai] LOOPS_API_KEY not set, skipping email")
        return False

    try:
        # Add/update contact in Loops
        with httpx.Client(timeout=15) as client:
            client.post(
                "https://app.loops.so/api/v1/contacts/create",
                headers={"Authorization": f"Bearer {LOOPS_API_KEY}"},
                json={
                    "email": email,
                    "firstName": name,
                    "mikai_domain": domain,
                    "mikai_score": score,
                    "mikai_gaps": gaps_count,
                    "mikai_tasks_total": tasks_total,
                    "mikai_report_url": report_url,
                    "mikai_status": "audit_delivered",
                    "source": "mikai_audit",
                },
            )

            # Fire event to trigger nurture sequence
            resp = client.post(
                "https://app.loops.so/api/v1/events/send",
                headers={"Authorization": f"Bearer {LOOPS_API_KEY}"},
                json={
                    "email": email,
                    "eventName": "mikai_audit_delivered",
                    "eventProperties": {
                        "domain": domain,
                        "score": score,
                        "gaps_count": gaps_count,
                        "tasks_total": tasks_total,
                        "report_url": report_url,
                    },
                },
            )
            print(f"[MiKai] Loops event sent for {email}: {resp.status_code}")
            return resp.status_code in (200, 201)

    except Exception as e:
        print(f"[MiKai] Loops error: {e}")
        return False


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


@router.post("/audit", response_model=WebhookResponse)
async def submit_audit(request: AuditRequest, background_tasks: BackgroundTasks):
    """
    Public endpoint — accept audit form submission.
    No API key required (called from landing page).
    """
    domain = _clean_domain(request.domain)

    if not domain or "." not in domain:
        return WebhookResponse(success=False, error="Invalid domain. Enter something like example.com")

    if not request.email or "@" not in request.email:
        return WebhookResponse(success=False, error="Invalid email address.")

    if not request.name.strip():
        return WebhookResponse(success=False, error="Name is required.")

    # Check for duplicate
    existing = _find_lead(domain)
    if existing and existing["status"] in ("pending", "running"):
        return WebhookResponse(
            success=True,
            data={"message": "Audit already in progress for this domain.", "domain": domain}
        )

    # Save lead
    leads = _load_leads()
    lead = {
        "domain": domain,
        "email": request.email.strip().lower(),
        "name": request.name.strip(),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "audit_path": None,
        "score": None,
        "gaps_count": None,
        "tasks_total": None,
        "sent_at": None,
        "error": None,
    }

    # Replace existing or append
    replaced = False
    for i, l in enumerate(leads):
        if l["domain"] == domain:
            leads[i] = lead
            replaced = True
            break
    if not replaced:
        leads.append(lead)

    _save_leads(leads)

    # Kick off audit in background
    background_tasks.add_task(_run_audit_background, domain)

    return WebhookResponse(
        success=True,
        data={
            "message": f"Audit queued for {domain}. Report will be sent to {request.email} within 24 hours.",
            "domain": domain,
        }
    )


# --- Authenticated endpoints below ---

@router.get("/leads", response_model=WebhookResponse, dependencies=[Depends(verify_api_key)])
async def list_leads():
    """List all audit leads."""
    leads = _load_leads()
    return WebhookResponse(success=True, data={
        "leads": leads,
        "total": len(leads),
        "pending": sum(1 for l in leads if l["status"] == "pending"),
        "sent": sum(1 for l in leads if l["status"] == "sent"),
        "failed": sum(1 for l in leads if l["status"] == "failed"),
    })


@router.get("/leads/{domain}", response_model=WebhookResponse, dependencies=[Depends(verify_api_key)])
async def get_lead(domain: str):
    """Get a specific lead + audit status."""
    lead = _find_lead(_clean_domain(domain))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return WebhookResponse(success=True, data=lead)


@router.post("/run/{domain}", response_model=WebhookResponse, dependencies=[Depends(verify_api_key)])
async def trigger_audit(domain: str, background_tasks: BackgroundTasks):
    """Manually re-trigger an audit for a domain."""
    clean = _clean_domain(domain)
    lead = _find_lead(clean)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found. Submit via /audit first.")

    lead["status"] = "pending"
    leads = _load_leads()
    for i, l in enumerate(leads):
        if l["domain"] == clean:
            leads[i]["status"] = "pending"
            break
    _save_leads(leads)

    background_tasks.add_task(_run_audit_background, clean)
    return WebhookResponse(success=True, data={"message": f"Audit re-triggered for {clean}"})
