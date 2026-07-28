from __future__ import annotations

import hashlib
import json
from typing import Any


def build_packet_fingerprint(
    *,
    profile_version: int,
    resume_version: int,
    answer_versions: dict[str, int],
    job_snapshot_hash: str,
    rendered_packet: str,
    cover_letter_version: int | None = None,
) -> dict[str, Any]:
    basis = {
        "profile_version": profile_version,
        "resume_version": resume_version,
        "cover_letter_version": cover_letter_version
        if cover_letter_version is not None
        else resume_version,
        "answer_versions": dict(sorted(answer_versions.items())),
        "job_snapshot_hash": job_snapshot_hash,
    }
    packet_hash = hashlib.sha256(
        json.dumps(
            {**basis, "rendered_packet": rendered_packet}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return {**basis, "packet_hash": packet_hash}
