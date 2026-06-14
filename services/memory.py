import sqlite3
import threading
from pathlib import Path
from services.config import config_service

class MemoryService:
    def __init__(self):
        self._lock = threading.Lock()
        db_path = config_service.data_path / "memory.db"
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS file_metadata (
                    path TEXT PRIMARY KEY,
                    tags TEXT,
                    subject TEXT
                )
            """)
            self._conn.commit()

    def update_vault_index(self, file_path, file_name, text, source_type=None):
        pass

    def readiness_score(self):
        return 0.0

    def get_weak_topics(self, limit=5):
        return []

    def get_weekly_stats(self):
        return {}

    def save_concept_edge(self, source, target, source_file):
        pass

    def get_knowledge_debt(self):
        return {}

memory_service = MemoryService()
