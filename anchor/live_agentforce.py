"""Thin LIVE Salesforce Agentforce client (Agent API) for the anchor study.

Endpoints follow the official Agent API Get Started guide (verified
Aug 2026): token from the org's My Domain ``/services/oauth2/token``
(client-credentials), Agent API calls against
``https://api.salesforce.com/einstein/ai-agent/v1`` with the agent id.
Secrets come ONLY from the environment: AGENTFORCE_CLIENT_ID /
AGENTFORCE_CLIENT_SECRET (the External Client App's consumer key/secret).

Agentforce does not expose token counts; the cost proxy is INVOCATION
COUNT (message turns). Only timing / counts / status are stored.
"""
from __future__ import annotations

import os
import time
import uuid

import requests

API_BASE = "https://api.salesforce.com/einstein/ai-agent/v1"


class LiveAgentforce:
    def __init__(self, domain: str, agent_id: str, api_version: str = "v1"):
        self._domain = domain.rstrip("/")
        self._agent_id = agent_id
        self._token = self._oauth_token()

    def _oauth_token(self) -> str:
        cid = os.environ.get("AGENTFORCE_CLIENT_ID")
        secret = os.environ.get("AGENTFORCE_CLIENT_SECRET")
        if not cid or not secret:
            raise RuntimeError(
                "Set AGENTFORCE_CLIENT_ID and AGENTFORCE_CLIENT_SECRET in "
                "the environment (External Client App consumer key/secret).")
        r = requests.post(f"{self._domain}/services/oauth2/token",
                          data={"grant_type": "client_credentials",
                                "client_id": cid, "client_secret": secret},
                          timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json"}

    def _open_session(self) -> str:
        url = f"{API_BASE}/agents/{self._agent_id}/sessions"
        r = requests.post(url, headers=self._headers(), json={
            "externalSessionKey": str(uuid.uuid4()),
            "instanceConfig": {"endpoint": self._domain},
            "streamingCapabilities": {"chunkTypes": ["Text"]},
            "bypassUser": True,
        }, timeout=60)
        r.raise_for_status()
        return r.json()["sessionId"]

    def _send(self, session_id: str, seq: int, text: str) -> dict:
        url = f"{API_BASE}/sessions/{session_id}/messages"
        t0 = time.perf_counter()
        r = requests.post(url, headers=self._headers(), json={
            "message": {"sequenceId": seq, "type": "Text", "text": text},
        }, timeout=120)
        r.raise_for_status()
        return {"latency_s": time.perf_counter() - t0, "invocations": 1,
                "tokens_in": 0, "tokens_out": 0, "status": "ok"}

    def _close(self, session_id: str) -> None:
        try:
            requests.delete(f"{API_BASE}/sessions/{session_id}",
                            headers={**self._headers(),
                                     "x-session-end-reason": "UserRequest"},
                            timeout=30)
        except requests.RequestException:
            pass

    def run_p2(self, task: str, cfg: dict) -> dict:
        """S1 single-stage: one message turn in one session."""
        sid = self._open_session()
        try:
            r = self._send(sid, 1, task)
        finally:
            self._close(sid)
        return {"pattern": "P2", **r}

    def run_p1(self, task: str, cfg: dict) -> dict:
        """Supervisor plan + N collaborator turns + synthesis turn."""
        n = int(cfg.get("n_collaborators", 2))
        sid = self._open_session()
        try:
            turns = [self._send(sid, i + 1, task) for i in range(n + 2)]
        finally:
            self._close(sid)
        return {"pattern": "P1",
                "latency_s": sum(t["latency_s"] for t in turns),
                "invocations": sum(t["invocations"] for t in turns),
                "tokens_in": 0, "tokens_out": 0,
                "status": "ok" if all(t["status"] == "ok" for t in turns)
                          else "partial"}
