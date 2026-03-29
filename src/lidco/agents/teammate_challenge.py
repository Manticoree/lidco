"""TeammateChallengeProtocol — structured disagreement between agents."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChallengeRequest:
    id: str
    challenger: str
    target: str
    finding: str
    rationale: str = ""
    created_at: str = ""


@dataclass
class ChallengeResponse:
    request_id: str
    responder: str
    accepted: bool
    counter: str = ""
    responded_at: str = ""


@dataclass
class ChallengeLog:
    entries: list[tuple[ChallengeRequest, Optional[ChallengeResponse]]] = field(
        default_factory=list
    )

    @property
    def accepted_count(self) -> int:
        return sum(
            1
            for _, resp in self.entries
            if resp is not None and resp.accepted
        )

    @property
    def rejected_count(self) -> int:
        return sum(
            1
            for _, resp in self.entries
            if resp is not None and not resp.accepted
        )

    @property
    def pending_count(self) -> int:
        return sum(1 for _, resp in self.entries if resp is None)


class ChallengeProtocol:
    """Protocol for agents to challenge each other's findings."""

    def __init__(self, mailbox: object = None) -> None:
        self._mailbox = mailbox
        self._log = ChallengeLog()

    def issue(
        self,
        challenger: str,
        target: str,
        finding: str,
        rationale: str = "",
    ) -> ChallengeRequest:
        """Create a ChallengeRequest; send MailMessage to target via mailbox if available; log it."""
        req = ChallengeRequest(
            id=uuid.uuid4().hex[:12],
            challenger=challenger,
            target=target,
            finding=finding,
            rationale=rationale,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self._log.entries.append((req, None))

        if self._mailbox is not None:
            msg = f"CHALLENGE from {challenger}: {finding}"
            if rationale:
                msg += f" | Rationale: {rationale}"
            self._mailbox.send(to=target, from_=challenger, message=msg)

        return req

    def respond(
        self,
        target: str,
        request_id: str,
        accepted: bool,
        counter: str = "",
    ) -> ChallengeResponse:
        """Create response; send reply via mailbox; update log entry."""
        resp = ChallengeResponse(
            request_id=request_id,
            responder=target,
            accepted=accepted,
            counter=counter,
            responded_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

        # Update the log entry
        for i, (req, existing_resp) in enumerate(self._log.entries):
            if req.id == request_id:
                self._log.entries[i] = (req, resp)
                break

        if self._mailbox is not None:
            status = "ACCEPTED" if accepted else "REJECTED"
            msg = f"CHALLENGE_RESPONSE {status} for {request_id}"
            if counter:
                msg += f" | Counter: {counter}"
            # Find the original challenger
            challenger = ""
            for req, _ in self._log.entries:
                if req.id == request_id:
                    challenger = req.challenger
                    break
            if challenger:
                self._mailbox.send(to=challenger, from_=target, message=msg)

        return resp

    def get_log(self) -> ChallengeLog:
        """Return the full challenge log."""
        return self._log

    def get_pending(self, target: str) -> list[ChallengeRequest]:
        """Return unanswered challenges directed at target."""
        return [
            req
            for req, resp in self._log.entries
            if req.target == target and resp is None
        ]
