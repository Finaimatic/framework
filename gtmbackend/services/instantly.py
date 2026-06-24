"""Instantly.ai REST API v2 client."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, quote

import httpx

BASE_URL = "https://api.instantly.ai"


# ─── Types ─────────────────────────────────────────────────────────────────

@dataclass
class InstantlyCampaign:
    id: str
    name: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class InstantlyLead:
    email: str
    first_name: str | None = None
    last_name: str | None = None
    company_name: str | None = None
    title: str | None = None
    custom_variables: dict[str, str] = field(default_factory=dict)


@dataclass
class InstantlyEmailAccount:
    id: str
    email: str
    status: str


@dataclass
class CampaignAnalytics:
    campaign_id: str
    total_leads: int = 0
    contacted: int = 0
    emails_sent: int = 0
    emails_read: int = 0
    replies: int = 0
    bounced: int = 0


@dataclass
class SequenceStep:
    body: str
    subject: str | None = None
    delay_days: int | None = None
    variant_label: str | None = None


@dataclass
class CreateCampaignOpts:
    name: str
    account_ids: list[str] = field(default_factory=list)
    sequences: list[SequenceStep] = field(default_factory=list)
    schedule: dict[str, Any] | None = None


@dataclass
class LeadStatus:
    email: str
    status: str
    lead_id: str | None = None
    opened_at: str | None = None
    replied_at: str | None = None
    bounced_at: str | None = None


@dataclass
class InboxReply:
    id: str | None = None
    campaign_id: str | None = None
    lead_email: str | None = None
    from_email: str | None = None
    to_email: str | None = None
    subject: str | None = None
    body: str | None = None
    body_text: str | None = None
    received_at: str | None = None
    thread_id: str | None = None


# ─── Service ───────────────────────────────────────────────────────────────

class InstantlyService:
    def is_available(self) -> bool:
        return bool(os.environ.get("INSTANTLY_API_KEY"))

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        api_key = os.environ.get("INSTANTLY_API_KEY")
        if not api_key:
            raise RuntimeError("INSTANTLY_API_KEY environment variable must be set")

        with httpx.Client() as client:
            response = client.request(
                method,
                f"{BASE_URL}{path}",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=body,
                timeout=30,
            )

        if not response.is_success:
            raise RuntimeError(f"Instantly API error ({response.status_code}): {response.text}")

        return response.json()

    # ─── Campaigns ─────────────────────────────────────────────────────────

    def create_campaign(self, opts: CreateCampaignOpts) -> InstantlyCampaign:
        data = {"name": opts.name}
        if opts.account_ids:
            data["account_ids"] = opts.account_ids
        if opts.sequences:
            data["sequences"] = [
                {k: v for k, v in {
                    "body": s.body,
                    "subject": s.subject,
                    "delay_days": s.delay_days,
                    "variant_label": s.variant_label,
                }.items() if v is not None}
                for s in opts.sequences
            ]
        if opts.schedule:
            data["schedule"] = opts.schedule
        raw = self._request("POST", "/api/v2/campaigns", data)
        return InstantlyCampaign(**{k: raw[k] for k in ("id", "name", "status") if k in raw} |
                                  {k: raw.get(k) for k in ("created_at", "updated_at")})

    def get_campaign(self, campaign_id: str) -> InstantlyCampaign:
        raw = self._request("GET", f"/api/v2/campaigns/{campaign_id}")
        return InstantlyCampaign(**{k: raw[k] for k in ("id", "name", "status") if k in raw} |
                                  {k: raw.get(k) for k in ("created_at", "updated_at")})

    def list_campaigns(self) -> list[InstantlyCampaign]:
        raw = self._request("GET", "/api/v2/campaigns")
        items = raw.get("items") or []
        return [
            InstantlyCampaign(**{k: item[k] for k in ("id", "name", "status") if k in item} |
                               {k: item.get(k) for k in ("created_at", "updated_at")})
            for item in items
        ]

    def pause_campaign(self, campaign_id: str) -> None:
        self._request("POST", f"/api/v2/campaigns/{campaign_id}/pause")

    def resume_campaign(self, campaign_id: str) -> None:
        self._request("POST", f"/api/v2/campaigns/{campaign_id}/resume")

    # ─── Leads ─────────────────────────────────────────────────────────────

    def add_leads_to_campaign(self, campaign_id: str, leads: list[InstantlyLead]) -> None:
        batch_size = 1000
        for i in range(0, len(leads), batch_size):
            batch = leads[i : i + batch_size]
            self._request("POST", "/api/v2/leads/bulk", {
                "campaign_id": campaign_id,
                "leads": [
                    {k: v for k, v in {
                        "email": lead.email,
                        "first_name": lead.first_name,
                        "last_name": lead.last_name,
                        "company_name": lead.company_name,
                        "title": lead.title,
                        "custom_variables": lead.custom_variables or None,
                    }.items() if v is not None}
                    for lead in batch
                ],
            })

    def list_leads(self, campaign_id: str, limit: int = 100) -> list[LeadStatus]:
        # Instantly uses POST for listing leads (non-standard)
        raw = self._request("POST", "/api/v2/leads/list", {
            "campaign_id": campaign_id,
            "limit": limit,
        })
        items = raw.get("items") or []
        return [
            LeadStatus(**{k: item.get(k) for k in (
                "email", "status", "lead_id", "opened_at", "replied_at", "bounced_at"
            )})
            for item in items
        ]

    def get_lead_status(self, lead_id: str) -> LeadStatus:
        raw = self._request("GET", f"/api/v2/leads/{lead_id}")
        return LeadStatus(**{k: raw.get(k) for k in (
            "email", "status", "lead_id", "opened_at", "replied_at", "bounced_at"
        )})

    # ─── Email Accounts ────────────────────────────────────────────────────

    def list_email_accounts(self) -> list[InstantlyEmailAccount]:
        raw = self._request("GET", "/api/v2/accounts")
        items = raw.get("items") or []
        return [
            InstantlyEmailAccount(id=item["id"], email=item["email"], status=item["status"])
            for item in items
        ]

    # ─── Unibox / Inbox ────────────────────────────────────────────────────

    def list_inbox_replies(self, lookback_hours: int, limit: int = 100) -> list[InboxReply]:
        cutoff_ms = int(time.time() * 1000) - lookback_hours * 3_600_000
        since = _ms_to_iso(cutoff_ms)
        path = (
            f"/api/v2/unibox/emails"
            f"?direction=inbound&since={quote(since)}&limit={limit}"
        )
        raw = self._request("GET", path)
        items = raw.get("items") or []
        return [
            InboxReply(**{k: item.get(k) for k in (
                "id", "campaign_id", "lead_email", "from_email", "to_email",
                "subject", "body", "body_text", "received_at", "thread_id",
            )})
            for item in items
        ]

    # ─── Analytics ─────────────────────────────────────────────────────────

    def get_campaign_analytics(self, campaign_id: str) -> CampaignAnalytics:
        raw = self._request("GET", f"/api/v2/campaigns/analytics?campaign_id={campaign_id}")
        items = raw.get("items") or []
        if items:
            item = items[0]
            return CampaignAnalytics(**{k: item.get(k, 0) for k in (
                "campaign_id", "total_leads", "contacted",
                "emails_sent", "emails_read", "replies", "bounced",
            )})
        return CampaignAnalytics(campaign_id=campaign_id)


def _ms_to_iso(ms: int) -> str:
    import datetime
    dt = datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


instantly_service = InstantlyService()
