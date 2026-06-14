import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from services.config import config_service

class LeanMemory:
    def __init__(self):
        db_path = Path(config_service.get("DATA_DIR", str(config_service.data_path)))
        db_path.mkdir(parents=True, exist_ok=True)
        self.db_file = db_path / "companion.db"
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_file, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Table to store extracted nodes and their generated content
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS study_nodes (
                    node_id TEXT PRIMARY KEY,
                    title TEXT,
                    raw_content TEXT,
                    parent_id TEXT,
                    fact TEXT,
                    question TEXT,
                    example TEXT,
                    mnemonic TEXT,
                    last_played REAL DEFAULT 0.0,
                    times_played INTEGER DEFAULT 0,
                    questions_asked INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0
                )
            ''')
            # Table to store general memory/stats
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_stats (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            # Table to store chat sessions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT,
                    messages TEXT,
                    created_at REAL
                )
            ''')
            # Table to store generated visuals history for rotation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS generated_visuals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    template_name TEXT,
                    generated_at REAL
                )
            ''')
            conn.commit()
            self._migrate(conn)

    def _migrate(self, conn):
        """Additive schema upgrades. Idempotent."""
        existing = {r[1] for r in conn.execute("PRAGMA table_info(chat_sessions)").fetchall()}
        new_cols = [
            ("document_filename",        "TEXT"),
            ("extracted_text",           "TEXT"),
            ("cache_name",               "TEXT"),
            ("cache_expires_at",         "INTEGER DEFAULT 0"),
            ("cache_model",              "TEXT"),
            ("cache_system_prompt_hash", "TEXT"),
            ("cache_api_key_id",         "TEXT"),
        ]
        for col, ddl in new_cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE chat_sessions ADD COLUMN {col} {ddl}")
        conn.commit()

    def upsert_node(self, node_id: str, title: str, raw_content: str, parent_id: Optional[str] = None):
        with self._get_conn() as conn:
            conn.execute('''
                INSERT INTO study_nodes (node_id, title, raw_content, parent_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    title=excluded.title,
                    raw_content=excluded.raw_content,
                    parent_id=excluded.parent_id
            ''', (node_id, title, raw_content, parent_id))
            conn.commit()

    def update_generated_content(self, node_id: str, fact: str, question: str, example: str, mnemonic: str):
        with self._get_conn() as conn:
            conn.execute('''
                UPDATE study_nodes
                SET fact=?, question=?, example=?, mnemonic=?
                WHERE node_id=?
            ''', (fact, question, example, mnemonic, node_id))
            conn.commit()

    def get_node_without_content(self) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('''
                SELECT * FROM study_nodes
                WHERE fact IS NULL OR fact = '' OR fact = 'Failed to parse content.'
                LIMIT 1
            ''').fetchone()
            return dict(row) if row else None

    def get_all_nodes_without_content(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT * FROM study_nodes
                WHERE fact IS NULL OR fact = '' OR fact = 'Failed to parse content.'
            ''').fetchall()
            return [dict(r) for r in rows]

    def get_next_node_to_play(self) -> Optional[Dict[str, Any]]:
        """Returns the node that was played the least, or answered incorrectly."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            # Prioritize: never played > answered wrong (correct_answers < questions_asked) > oldest played
            row = conn.execute('''
                SELECT * FROM study_nodes
                WHERE fact IS NOT NULL AND fact != ''
                ORDER BY 
                    times_played ASC,
                    (questions_asked - correct_answers) DESC,
                    last_played ASC
                LIMIT 1
            ''').fetchone()
            return dict(row) if row else None

    def mark_played(self, node_id: str):
        import time
        with self._get_conn() as conn:
            conn.execute('''
                UPDATE study_nodes
                SET times_played = times_played + 1, last_played = ?
                WHERE node_id = ?
            ''', (time.time(), node_id))
            conn.commit()

    def mark_question_answered(self, node_id: str, correct: bool):
        with self._get_conn() as conn:
            conn.execute(f'''
                UPDATE study_nodes
                SET questions_asked = questions_asked + 1,
                    correct_answers = correct_answers + {1 if correct else 0}
                WHERE node_id = ?
            ''', (node_id,))
            conn.commit()

    def get_nodes_stats(self) -> Dict[str, int]:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM study_nodes").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM study_nodes WHERE fact IS NULL OR fact = '' OR fact = 'Failed to parse content.'").fetchone()[0]
            completed = total - pending
            return {"total": total, "pending": pending, "completed": completed}

    def get_chat_sessions(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM chat_sessions ORDER BY created_at DESC").fetchall()
            sessions = []
            for r in rows:
                s = dict(r)
                try:
                    s["messages"] = json.loads(s["messages"])
                except Exception:
                    s["messages"] = []
                sessions.append(s)
            return sessions

    def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM chat_sessions WHERE session_id=?", (session_id,)).fetchone()
            if row:
                s = dict(row)
                try:
                    s["messages"] = json.loads(s["messages"])
                except Exception:
                    s["messages"] = []
                return s
            return None

    def save_chat_session(self, session_id: str, title: str, messages: List[Dict[str, Any]]):
        import time
        with self._get_conn() as conn:
            messages_str = json.dumps(messages)
            conn.execute('''
                INSERT INTO chat_sessions (session_id, title, messages, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    title=excluded.title,
                    messages=excluded.messages
            ''', (session_id, title, messages_str, time.time()))
            conn.commit()

    def delete_chat_session(self, session_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM chat_sessions WHERE session_id=?", (session_id,))
            conn.commit()

    def log_generated_visual(self, source: str, template_name: str):
        import time
        with self._get_conn() as conn:
            conn.execute('''
                INSERT INTO generated_visuals (source, template_name, generated_at)
                VALUES (?, ?, ?)
            ''', (source, template_name, time.time()))
            conn.commit()

    def get_recent_templates(self, source: str, limit: int = 5) -> List[str]:
        with self._get_conn() as conn:
            rows = conn.execute('''
                SELECT template_name FROM generated_visuals
                WHERE source = ?
                ORDER BY generated_at DESC
                LIMIT ?
            ''', (source, limit)).fetchall()
            return [r[0] for r in rows]

    # ── Document + cache binding on chat sessions ────────────────────────────

    def attach_document(self, session_id: str, filename: str, extracted_text: str):
        """Pin a document to a session. Creates the session row if missing."""
        import time as _t
        with self._get_conn() as conn:
            conn.execute('''
                INSERT INTO chat_sessions (session_id, title, messages, created_at,
                                          document_filename, extracted_text,
                                          cache_name, cache_expires_at, cache_model,
                                          cache_system_prompt_hash, cache_api_key_id)
                VALUES (?, ?, ?, ?, ?, ?, NULL, 0, NULL, NULL, NULL)
                ON CONFLICT(session_id) DO UPDATE SET
                    document_filename=excluded.document_filename,
                    extracted_text=excluded.extracted_text,
                    cache_name=NULL, cache_expires_at=0, cache_model=NULL,
                    cache_system_prompt_hash=NULL, cache_api_key_id=NULL
            ''', (session_id, filename, json.dumps([]), _t.time(), filename, extracted_text))
            conn.commit()

    def get_session_doc(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return cache + doc fields for one session, or None if missing."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('''
                SELECT document_filename, extracted_text, cache_name, cache_expires_at,
                       cache_model, cache_system_prompt_hash, cache_api_key_id
                FROM chat_sessions WHERE session_id=?
            ''', (session_id,)).fetchone()
            return dict(row) if row else None

    def update_cache(self, session_id: str, cache_name: Optional[str], expires_at: int,
                     model: Optional[str], system_prompt_hash: Optional[str],
                     api_key_id: Optional[str]):
        with self._get_conn() as conn:
            conn.execute('''
                UPDATE chat_sessions
                SET cache_name=?, cache_expires_at=?, cache_model=?,
                    cache_system_prompt_hash=?, cache_api_key_id=?
                WHERE session_id=?
            ''', (cache_name, expires_at, model, system_prompt_hash, api_key_id, session_id))
            conn.commit()

    def clear_cache(self, session_id: str):
        """Forget the cache reference without touching messages or the doc."""
        self.update_cache(session_id, None, 0, None, None, None)

memory_layer = LeanMemory()
