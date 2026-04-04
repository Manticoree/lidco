"""NotionClient — simulated Notion API client (stdlib only)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Block:
    """A Notion block (paragraph, heading, etc.)."""

    id: str
    type: str  # "paragraph" | "heading_1" | "heading_2" | "code" | "bulleted_list"
    content: str
    parent_id: str | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class Page:
    """A Notion page."""

    id: str
    title: str
    content: str = ""
    parent_id: str | None = None
    blocks: list[Block] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class Database:
    """A Notion database."""

    id: str
    title: str
    page_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class NotionClient:
    """Simulated Notion API client for local development.

    Parameters
    ----------
    api_key:
        Optional API key (simulated; not sent anywhere).
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._pages: dict[str, Page] = {}
        self._blocks: dict[str, Block] = {}
        self._databases: dict[str, Database] = {}

    # ------------------------------------------------------------------ pages

    def get_page(self, page_id: str) -> Page:
        """Retrieve a page by ID.

        Raises
        ------
        KeyError
            If the page does not exist.
        """
        if page_id not in self._pages:
            raise KeyError(f"Page not found: {page_id}")
        return self._pages[page_id]

    def create_page(
        self,
        parent: str | None,
        title: str,
        content: str = "",
    ) -> Page:
        """Create a new page.

        Parameters
        ----------
        parent:
            Parent page or database ID.  May be ``None`` for root pages.
        title:
            Page title.
        content:
            Initial text content.

        Raises
        ------
        ValueError
            If *title* is empty.
        """
        if not title.strip():
            raise ValueError("Title must not be empty")
        page_id = uuid.uuid4().hex[:12]
        now = time.time()
        page = Page(
            id=page_id,
            title=title,
            content=content,
            parent_id=parent,
            created_at=now,
            updated_at=now,
        )
        self._pages[page_id] = page
        # If parent is a database, add to its page list
        if parent and parent in self._databases:
            db = self._databases[parent]
            self._databases[parent] = Database(
                id=db.id,
                title=db.title,
                page_ids=[*db.page_ids, page_id],
                created_at=db.created_at,
            )
        return page

    def update_page(self, page_id: str, title: str | None = None, content: str | None = None) -> Page:
        """Update an existing page.

        Raises
        ------
        KeyError
            If the page does not exist.
        """
        old = self.get_page(page_id)
        updated = Page(
            id=old.id,
            title=title if title is not None else old.title,
            content=content if content is not None else old.content,
            parent_id=old.parent_id,
            blocks=old.blocks,
            created_at=old.created_at,
            updated_at=time.time(),
        )
        self._pages[page_id] = updated
        return updated

    def delete_page(self, page_id: str) -> bool:
        """Delete a page.  Returns True if it existed."""
        if page_id in self._pages:
            del self._pages[page_id]
            return True
        return False

    # ---------------------------------------------------------------- search

    def search(self, query: str) -> list[Page]:
        """Search pages by title or content (case-insensitive substring)."""
        q = query.lower()
        return [
            p
            for p in self._pages.values()
            if q in p.title.lower() or q in p.content.lower()
        ]

    # ---------------------------------------------------------------- blocks

    def get_block(self, block_id: str) -> Block:
        """Retrieve a block by ID.

        Raises
        ------
        KeyError
            If the block does not exist.
        """
        if block_id not in self._blocks:
            raise KeyError(f"Block not found: {block_id}")
        return self._blocks[block_id]

    def add_block(self, page_id: str, block_type: str, content: str) -> Block:
        """Add a block to a page.

        Raises
        ------
        KeyError
            If the page does not exist.
        """
        page = self.get_page(page_id)
        block_id = uuid.uuid4().hex[:12]
        block = Block(id=block_id, type=block_type, content=content, parent_id=page_id)
        self._blocks[block_id] = block
        new_blocks = [*page.blocks, block]
        self._pages[page_id] = Page(
            id=page.id,
            title=page.title,
            content=page.content,
            parent_id=page.parent_id,
            blocks=new_blocks,
            created_at=page.created_at,
            updated_at=time.time(),
        )
        return block

    # ------------------------------------------------------------- databases

    def list_databases(self) -> list[Database]:
        """Return all databases."""
        return list(self._databases.values())

    def create_database(self, title: str) -> Database:
        """Create a new database.

        Raises
        ------
        ValueError
            If *title* is empty.
        """
        if not title.strip():
            raise ValueError("Title must not be empty")
        db_id = uuid.uuid4().hex[:12]
        db = Database(id=db_id, title=title)
        self._databases[db_id] = db
        return db
