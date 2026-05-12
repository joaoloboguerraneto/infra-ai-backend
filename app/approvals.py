"""
Gerenciamento de aprovações com TTL.
Armazena tokens em memória (POC) — para produção usar Redis ou DynamoDB.
"""
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional


TTL_SECONDS = 1800  # 30 minutos


@dataclass
class ApprovalRequest:
    request_id:     str
    token:          str
    org:            str
    project:        str
    repo_name:      str
    requester_email: str
    approver_email: str
    created_at:     float = field(default_factory=time.time)
    approved:       bool  = False
    executed:       bool  = False

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > TTL_SECONDS

    def expires_in_minutes(self) -> int:
        elapsed = time.time() - self.created_at
        remaining = TTL_SECONDS - elapsed
        return max(0, int(remaining / 60))


class ApprovalStore:
    """Thread-safe in-memory store de aprovações."""

    def __init__(self):
        self._store: dict[str, ApprovalRequest] = {}

    def create(
        self,
        org:             str,
        project:         str,
        repo_name:       str,
        requester_email: str,
        approver_email:  str,
    ) -> ApprovalRequest:
        request_id = secrets.token_urlsafe(8)
        token      = secrets.token_urlsafe(16)

        req = ApprovalRequest(
            request_id=request_id,
            token=token,
            org=org,
            project=project,
            repo_name=repo_name,
            requester_email=requester_email,
            approver_email=approver_email,
        )
        self._store[request_id] = req
        return req

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        req = self._store.get(request_id)
        if req and req.is_expired():
            del self._store[request_id]
            return None
        return req

    def confirm(self, request_id: str, token: str) -> Optional[ApprovalRequest]:
        """Valida token e marca como aprovado. Retorna None se inválido/expirado."""
        req = self.get(request_id)
        if req is None:
            return None
        if req.token != token:
            return None
        if req.approved:
            return None
        req.approved = True
        return req

    def mark_executed(self, request_id: str):
        req = self._store.get(request_id)
        if req:
            req.executed = True

    def pending(self) -> list[ApprovalRequest]:
        """Lista aprovações pendentes não expiradas."""
        self._cleanup()
        return [r for r in self._store.values() if not r.executed]

    def _cleanup(self):
        expired = [rid for rid, r in self._store.items() if r.is_expired()]
        for rid in expired:
            del self._store[rid]


# Instância global
approval_store = ApprovalStore()