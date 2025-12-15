"""SQLite FTS5 full-text search for transcripts.

Provides fast keyword search across all indexed transcripts.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from podx.domain.models.transcript import Transcript


class TranscriptDatabase:
    """SQLite FTS5 database for full-text transcript search."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize transcript database.

        Args:
            db_path: Path to SQLite database file.
                    Defaults to ~/.podx/transcripts.db
        """
        if db_path is None:
            podx_dir = Path.home() / ".podx"
            podx_dir.mkdir(parents=True, exist_ok=True)
            db_path = podx_dir / "transcripts.db"

        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema with FTS5 tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create metadata table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT UNIQUE NOT NULL,
                title TEXT,
                show_name TEXT,
                date TEXT,
                duration REAL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create FTS5 virtual table for full-text search
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
                episode_id,
                speaker,
                text,
                timestamp,
                content='',
                tokenize='porter unicode61'
            )
            """
        )

        # Create triggers to keep FTS table in sync
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT NOT NULL,
                speaker TEXT,
                text TEXT NOT NULL,
                timestamp REAL,
                FOREIGN KEY(episode_id) REFERENCES episodes(episode_id)
            )
            """
        )

        conn.commit()
        conn.close()

    def index_transcript(
        self,
        episode_id: str,
        transcript: Transcript,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Index a transcript for searching.

        Args:
            episode_id: Unique episode identifier
            transcript: Transcript to index
            metadata: Optional episode metadata (title, show, date, etc.)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Extract metadata
        title = metadata.get("title", "") if metadata else ""
        show_name = metadata.get("show_name", "") if metadata else ""
        date = metadata.get("date", "") if metadata else ""
        duration = metadata.get("duration", 0.0) if metadata else 0.0
        metadata_json = json.dumps(metadata) if metadata else "{}"

        # Insert or update episode
        cursor.execute(
            """
            INSERT OR REPLACE INTO episodes
            (episode_id, title, show_name, date, duration, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (episode_id, title, show_name, date, duration, metadata_json),
        )

        # Delete existing segments for this episode
        cursor.execute("DELETE FROM segments WHERE episode_id = ?", (episode_id,))
        cursor.execute("DELETE FROM transcripts_fts WHERE episode_id = ?", (episode_id,))

        # Index segments
        for segment in transcript.segments:
            speaker = getattr(segment, "speaker", None) or "Unknown"
            text = segment.text
            timestamp = segment.start

            # Insert into segments table
            cursor.execute(
                """
                INSERT INTO segments (episode_id, speaker, text, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (episode_id, speaker, text, timestamp),
            )

            # Insert into FTS table
            cursor.execute(
                """
                INSERT INTO transcripts_fts (episode_id, speaker, text, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (episode_id, speaker, text, str(timestamp)),
            )

        conn.commit()
        conn.close()

    def search(
        self,
        query: str,
        limit: int = 50,
        episode_filter: Optional[str] = None,
        speaker_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search transcripts with FTS5.

        Args:
            query: Search query (supports FTS5 syntax)
            limit: Maximum number of results
            episode_filter: Filter by episode ID (optional)
            speaker_filter: Filter by speaker name (optional)

        Returns:
            List of matching segments with metadata
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build query
        sql_parts = [
            """
            SELECT
                s.episode_id,
                s.speaker,
                s.text,
                s.timestamp,
                e.title,
                e.show_name,
                e.date,
                bm25(transcripts_fts) as rank
            FROM transcripts_fts
            JOIN segments s ON transcripts_fts.rowid = s.rowid
            JOIN episodes e ON s.episode_id = e.episode_id
            WHERE transcripts_fts MATCH ?
            """
        ]

        params: List[Any] = [query]

        if episode_filter:
            sql_parts.append("AND s.episode_id = ?")
            params.append(episode_filter)

        if speaker_filter:
            sql_parts.append("AND s.speaker LIKE ?")
            params.append(f"%{speaker_filter}%")

        sql_parts.append("ORDER BY rank LIMIT ?")
        params.append(limit)

        sql = " ".join(sql_parts)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append(
                {
                    "episode_id": row[0],
                    "speaker": row[1],
                    "text": row[2],
                    "timestamp": row[3],
                    "title": row[4],
                    "show_name": row[5],
                    "date": row[6],
                    "rank": row[7],
                }
            )

        conn.close()
        return results

    def get_episode_info(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get episode metadata.

        Args:
            episode_id: Episode identifier

        Returns:
            Episode metadata dict or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT title, show_name, date, duration, metadata
            FROM episodes
            WHERE episode_id = ?
            """,
            (episode_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "episode_id": episode_id,
            "title": row[0],
            "show_name": row[1],
            "date": row[2],
            "duration": row[3],
            "metadata": json.loads(row[4]) if row[4] else {},
        }

    def list_episodes(
        self, show_filter: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List indexed episodes.

        Args:
            show_filter: Filter by show name (optional)
            limit: Maximum number of episodes

        Returns:
            List of episode metadata dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if show_filter:
            cursor.execute(
                """
                SELECT episode_id, title, show_name, date, duration
                FROM episodes
                WHERE show_name LIKE ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (f"%{show_filter}%", limit),
            )
        else:
            cursor.execute(
                """
                SELECT episode_id, title, show_name, date, duration
                FROM episodes
                ORDER BY date DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "episode_id": row[0],
                "title": row[1],
                "show_name": row[2],
                "date": row[3],
                "duration": row[4],
            }
            for row in rows
        ]

    def delete_episode(self, episode_id: str) -> None:
        """Remove episode from index.

        Args:
            episode_id: Episode identifier
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM episodes WHERE episode_id = ?", (episode_id,))
        cursor.execute("DELETE FROM segments WHERE episode_id = ?", (episode_id,))
        cursor.execute("DELETE FROM transcripts_fts WHERE episode_id = ?", (episode_id,))

        conn.commit()
        conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics.

        Returns:
            Dict with episode count, segment count, etc.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM episodes")
        episode_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM segments")
        segment_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT show_name) FROM episodes")
        show_count = cursor.fetchone()[0]

        conn.close()

        return {
            "episodes": episode_count,
            "segments": segment_count,
            "shows": show_count,
        }
