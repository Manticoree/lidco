"""ArenaLeaderboard — track model comparison votes and suggest best models."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MODELS = ("openai/gpt-4o", "anthropic/claude-sonnet-4-6")
_MIN_APPEARANCES = 3


@dataclass
class VoteRecord:
    model_a: str
    model_b: str
    winner: str
    task_type: str
    prompt_hash: str
    timestamp: float


@dataclass
class ModelStats:
    model: str
    wins: int
    appearances: int
    win_rate: float
    task_type: str


class ArenaLeaderboard:
    """SQLite-backed leaderboard for arena model comparison votes."""

    _DEFAULT_DB = Path(".lidco/arena_leaderboard.db")

    _CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS votes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        model_a     TEXT NOT NULL,
        model_b     TEXT NOT NULL,
        winner      TEXT NOT NULL,
        task_type   TEXT NOT NULL,
        prompt_hash TEXT NOT NULL,
        timestamp   REAL NOT NULL
    )
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else self._DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(self._CREATE_SQL)
            conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_vote(self, vote: VoteRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO votes (model_a, model_b, winner, task_type, prompt_hash, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (vote.model_a, vote.model_b, vote.winner, vote.task_type,
                 vote.prompt_hash, vote.timestamp),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def stats(self, task_type: str) -> list[ModelStats]:
        """Return ModelStats for all models in the given task_type."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT model_a, model_b, winner FROM votes WHERE task_type=?",
                (task_type,),
            ).fetchall()

        appearances: dict[str, int] = {}
        wins: dict[str, int] = {}
        for row in rows:
            for m in (row["model_a"], row["model_b"]):
                appearances[m] = appearances.get(m, 0) + 1
            wins[row["winner"]] = wins.get(row["winner"], 0) + 1

        result = []
        for model, app_count in appearances.items():
            w = wins.get(model, 0)
            result.append(ModelStats(
                model=model,
                wins=w,
                appearances=app_count,
                win_rate=w / app_count if app_count > 0 else 0.0,
                task_type=task_type,
            ))
        return sorted(result, key=lambda s: s.win_rate, reverse=True)

    def best_model(self, task_type: str) -> str | None:
        """Return model with highest win_rate for task_type, or None if insufficient data."""
        stats_list = self.stats(task_type)
        for s in stats_list:
            if s.appearances >= _MIN_APPEARANCES:
                return s.model
        return None

    def leaderboard(self) -> list[ModelStats]:
        """Return aggregate stats across all task types."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT model_a, model_b, winner, task_type FROM votes"
            ).fetchall()

        appearances: dict[str, int] = {}
        wins: dict[str, int] = {}
        for row in rows:
            for m in (row["model_a"], row["model_b"]):
                appearances[m] = appearances.get(m, 0) + 1
            wins[row["winner"]] = wins.get(row["winner"], 0) + 1

        result = []
        for model, app_count in appearances.items():
            w = wins.get(model, 0)
            result.append(ModelStats(
                model=model,
                wins=w,
                appearances=app_count,
                win_rate=w / app_count if app_count > 0 else 0.0,
                task_type="all",
            ))
        return sorted(result, key=lambda s: s.win_rate, reverse=True)

    def suggest_models(self, task_type: str) -> tuple[str, str]:
        """Suggest top-2 models by win_rate for task_type.

        Falls back to DEFAULT_MODELS if fewer than 2 models have sufficient data.
        """
        stats_list = [s for s in self.stats(task_type) if s.appearances >= _MIN_APPEARANCES]
        if len(stats_list) >= 2:
            return stats_list[0].model, stats_list[1].model
        if len(stats_list) == 1:
            return stats_list[0].model, DEFAULT_MODELS[1]
        return DEFAULT_MODELS[0], DEFAULT_MODELS[1]
