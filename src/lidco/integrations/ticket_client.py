"""Linear/Jira ticket integration — Task 406."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Ticket:
    """Structured project management ticket."""

    ticket_id: str
    title: str
    status: str
    description: str
    assignee: str
    url: str


class TicketClient(ABC):
    """Abstract base for ticket system clients."""

    @abstractmethod
    def list_tickets(
        self,
        status: str | None = None,
        assignee: str | None = None,
        limit: int = 20,
    ) -> list[Ticket]:
        """List tickets optionally filtered by status and/or assignee."""

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> Ticket:
        """Fetch a single ticket by ID."""

    @abstractmethod
    def update_ticket(
        self,
        ticket_id: str,
        status: str | None = None,
        comment: str | None = None,
    ) -> Ticket:
        """Update a ticket's status and/or add a comment."""


# ---------------------------------------------------------------------------
# Linear implementation
# ---------------------------------------------------------------------------

_LINEAR_API = "https://api.linear.app/graphql"


class LinearClient(TicketClient):
    """Linear ticket client using the Linear GraphQL API.

    Reads ``LINEAR_API_KEY`` from environment.

    Raises:
        ValueError: If the API key is not configured.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("LINEAR_API_KEY", "")

    def list_tickets(
        self,
        status: str | None = None,
        assignee: str | None = None,
        limit: int = 20,
    ) -> list[Ticket]:
        """List Linear issues.

        Args:
            status: Optional state name filter (e.g. "In Progress").
            assignee: Optional assignee display name filter.
            limit: Max results (default 20).

        Returns:
            List of Ticket instances.

        Raises:
            ValueError: If API key is missing.
            RuntimeError: On API error.
        """
        self._require_key()
        filter_parts: list[str] = []
        if status:
            filter_parts.append(f'state: {{name: {{eq: "{status}"}}}}')
        if assignee:
            filter_parts.append(f'assignee: {{displayName: {{eq: "{assignee}"}}}}')
        filter_clause = ""
        if filter_parts:
            filter_clause = f"filter: {{{', '.join(filter_parts)}}}"

        query = f"""
        query {{
            issues({filter_clause} first: {limit}) {{
                nodes {{
                    id
                    title
                    state {{ name }}
                    description
                    assignee {{ displayName }}
                    url
                }}
            }}
        }}
        """
        data = self._graphql(query)
        nodes = (
            data.get("data", {})
            .get("issues", {})
            .get("nodes", [])
        )
        return [_parse_linear_issue(n) for n in nodes]

    def get_ticket(self, ticket_id: str) -> Ticket:
        """Fetch a single Linear issue.

        Args:
            ticket_id: The issue UUID or identifier.

        Returns:
            Ticket instance.

        Raises:
            ValueError: If API key is missing.
            RuntimeError: On API error or issue not found.
        """
        self._require_key()
        query = f"""
        query {{
            issue(id: "{ticket_id}") {{
                id
                title
                state {{ name }}
                description
                assignee {{ displayName }}
                url
            }}
        }}
        """
        data = self._graphql(query)
        issue = data.get("data", {}).get("issue")
        if not issue:
            raise RuntimeError(f"Linear issue not found: {ticket_id}")
        return _parse_linear_issue(issue)

    def update_ticket(
        self,
        ticket_id: str,
        status: str | None = None,
        comment: str | None = None,
    ) -> Ticket:
        """Update a Linear issue status and/or add a comment.

        Args:
            ticket_id: The issue UUID.
            status: New state name (resolved to state ID via API).
            comment: Comment body to add.

        Returns:
            Updated Ticket instance.

        Raises:
            ValueError: If API key is missing.
            RuntimeError: On API error.
        """
        self._require_key()

        if comment:
            mutation = f"""
            mutation {{
                commentCreate(input: {{issueId: "{ticket_id}", body: "{comment}"}}) {{
                    success
                }}
            }}
            """
            self._graphql(mutation)

        if status:
            mutation = f"""
            mutation {{
                issueUpdate(id: "{ticket_id}", input: {{stateId: "{status}"}}) {{
                    issue {{
                        id title
                        state {{ name }}
                        description
                        assignee {{ displayName }}
                        url
                    }}
                }}
            }}
            """
            data = self._graphql(mutation)
            issue = data.get("data", {}).get("issueUpdate", {}).get("issue")
            if issue:
                return _parse_linear_issue(issue)

        return self.get_ticket(ticket_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_key(self) -> None:
        if not self._api_key:
            raise ValueError(
                "LINEAR_API_KEY environment variable is not set."
            )

    def _graphql(self, query: str) -> dict[str, Any]:
        payload = json.dumps({"query": query}).encode("utf-8")
        req = urllib.request.Request(
            _LINEAR_API,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": self._api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Linear API HTTP error: {exc.code} {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Linear API request failed: {exc.reason}"
            ) from exc


# ---------------------------------------------------------------------------
# Jira implementation
# ---------------------------------------------------------------------------


class JiraClient(TicketClient):
    """Jira ticket client using the Jira REST API v3.

    Reads ``JIRA_URL`` and ``JIRA_TOKEN`` from environment.

    Raises:
        ValueError: If URL or token are not configured.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        user_email: str | None = None,
    ) -> None:
        self._base_url = (base_url or os.environ.get("JIRA_URL", "")).rstrip("/")
        self._token = token or os.environ.get("JIRA_TOKEN", "")
        self._email = user_email or os.environ.get("JIRA_EMAIL", "")

    def list_tickets(
        self,
        status: str | None = None,
        assignee: str | None = None,
        limit: int = 20,
    ) -> list[Ticket]:
        """List Jira issues using JQL.

        Args:
            status: Optional status filter (e.g. "In Progress").
            assignee: Optional assignee filter ("currentUser()" or account ID).
            limit: Max results.

        Returns:
            List of Ticket instances.

        Raises:
            ValueError: If URL or token missing.
            RuntimeError: On API error.
        """
        self._require_config()
        jql_parts = []
        if status:
            jql_parts.append(f'status = "{status}"')
        if assignee:
            jql_parts.append(f'assignee = "{assignee}"')
        jql = " AND ".join(jql_parts) if jql_parts else "order by updated DESC"

        params = urllib.parse.urlencode({
            "jql": jql,
            "maxResults": limit,
            "fields": "summary,status,description,assignee",
        })
        url = f"{self._base_url}/rest/api/3/search?{params}"
        data = self._request("GET", url)
        issues = data.get("issues", [])
        return [_parse_jira_issue(i) for i in issues]

    def get_ticket(self, ticket_id: str) -> Ticket:
        """Fetch a single Jira issue.

        Args:
            ticket_id: Jira issue key (e.g. "PROJ-123").

        Returns:
            Ticket instance.

        Raises:
            ValueError: If URL or token missing.
            RuntimeError: On API error.
        """
        self._require_config()
        url = f"{self._base_url}/rest/api/3/issue/{ticket_id}?fields=summary,status,description,assignee"
        data = self._request("GET", url)
        return _parse_jira_issue(data)

    def update_ticket(
        self,
        ticket_id: str,
        status: str | None = None,
        comment: str | None = None,
    ) -> Ticket:
        """Update Jira issue status and/or add a comment.

        Args:
            ticket_id: Jira issue key.
            status: Transition name to apply.
            comment: Comment body.

        Returns:
            Updated Ticket instance.

        Raises:
            ValueError: If URL or token missing.
            RuntimeError: On API error.
        """
        self._require_config()

        if comment:
            url = f"{self._base_url}/rest/api/3/issue/{ticket_id}/comment"
            self._request("POST", url, {"body": {"type": "doc", "version": 1, "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": comment}]}
            ]}})

        if status:
            # Fetch available transitions
            trans_url = f"{self._base_url}/rest/api/3/issue/{ticket_id}/transitions"
            trans_data = self._request("GET", trans_url)
            transitions = trans_data.get("transitions", [])
            matching = [t for t in transitions if t.get("name", "").lower() == status.lower()]
            if matching:
                tid = matching[0]["id"]
                self._request("POST", trans_url, {"transition": {"id": tid}})

        return self.get_ticket(ticket_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_config(self) -> None:
        missing = []
        if not self._base_url:
            missing.append("JIRA_URL")
        if not self._token:
            missing.append("JIRA_TOKEN")
        if missing:
            raise ValueError(
                f"Jira configuration missing: {', '.join(missing)}"
            )

    def _request(
        self, method: str, url: str, body: dict | None = None
    ) -> dict[str, Any]:
        import base64
        if self._email:
            credentials = base64.b64encode(
                f"{self._email}:{self._token}".encode()
            ).decode()
            auth = f"Basic {credentials}"
        else:
            auth = f"Bearer {self._token}"

        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": auth,
                "Accept": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read().decode("utf-8")
                return json.loads(resp_body) if resp_body.strip() else {}
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Jira API HTTP error: {exc.code} {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Jira API request failed: {exc.reason}"
            ) from exc


# ---------------------------------------------------------------------------
# Module-level parse helpers
# ---------------------------------------------------------------------------

def _parse_linear_issue(raw: dict) -> Ticket:
    state = raw.get("state") or {}
    assignee = raw.get("assignee") or {}
    return Ticket(
        ticket_id=str(raw.get("id", "")),
        title=str(raw.get("title", "")),
        status=str(state.get("name", "")),
        description=str(raw.get("description") or ""),
        assignee=str(assignee.get("displayName", "")),
        url=str(raw.get("url", "")),
    )


def _parse_jira_issue(raw: dict) -> Ticket:
    fields = raw.get("fields") or {}
    status = (fields.get("status") or {}).get("name", "")
    assignee_obj = fields.get("assignee") or {}
    assignee = assignee_obj.get("displayName", "") or assignee_obj.get("name", "")
    desc_obj = fields.get("description") or {}
    # description can be Atlassian Document Format or plain string
    if isinstance(desc_obj, str):
        description = desc_obj
    elif isinstance(desc_obj, dict):
        # Extract plain text from ADF
        description = _extract_adf_text(desc_obj)
    else:
        description = ""

    issue_key = raw.get("key") or str(raw.get("id", ""))
    base = ""  # url not available from fields
    return Ticket(
        ticket_id=issue_key,
        title=str(fields.get("summary", "")),
        status=status,
        description=description,
        assignee=assignee,
        url=base,
    )


def _extract_adf_text(node: dict) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if node.get("type") == "text":
        return node.get("text", "")
    result = []
    for child in node.get("content", []):
        result.append(_extract_adf_text(child))
    return " ".join(result).strip()


# Need this for Jira URL building
import urllib.parse  # noqa: E402
