# SPDX-License-Identifier: Apache-2.0
"""Tamper-evident append-only audit chain (PRD 15, 30.2, AC-17, AC-52).

Each event stores the hash of its predecessor. Payloads hold references and hashes, never
whole resident records. Verification detects edits, deletions and reordering.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

GENESIS = "0" * 64


@dataclass(frozen=True)
class AuditRecord:
    seq: int
    prev_hash: str
    actor: str
    role: str
    action: str
    entity: str
    entity_id: str
    at_utc: str
    request_id: str
    reason: str
    detail_hash: str  # hash of before/after payload kept elsewhere; not the payload itself
    hash: str


def digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _record_hash(prev: str, fields: dict) -> str:
    return hashlib.sha256((prev + json.dumps(fields, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()


def append(chain: list[AuditRecord], *, actor: str, role: str, action: str, entity: str, entity_id: str,
           at_utc: str, request_id: str, reason: str = "", detail: object = None) -> AuditRecord:
    prev = chain[-1].hash if chain else GENESIS
    fields = dict(seq=len(chain) + 1, actor=actor, role=role, action=action, entity=entity, entity_id=entity_id,
                  at_utc=at_utc, request_id=request_id, reason=reason, detail_hash=digest(detail))
    rec = AuditRecord(prev_hash=prev, hash=_record_hash(prev, fields), **fields)
    chain.append(rec)
    return rec


def verify(chain: list[AuditRecord]) -> tuple[bool, int | None]:
    """Return (ok, first_bad_seq)."""
    prev = GENESIS
    for i, rec in enumerate(chain, start=1):
        fields = dict(seq=rec.seq, actor=rec.actor, role=rec.role, action=rec.action, entity=rec.entity,
                      entity_id=rec.entity_id, at_utc=rec.at_utc, request_id=rec.request_id, reason=rec.reason,
                      detail_hash=rec.detail_hash)
        if rec.seq != i or rec.prev_hash != prev or rec.hash != _record_hash(prev, fields):
            return False, rec.seq
        prev = rec.hash
    return True, None
