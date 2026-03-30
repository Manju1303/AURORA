import sqlite3
import os
from datetime import datetime

class MemoryManager:
    def __init__(self, db_path="aurora_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database for long-term memory."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Table for key-value facts (Name, Age, etc.)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS persistent_facts (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TEXT
                    )
                """)
                # Table for unstructured preferences or traits
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT,
                        content TEXT,
                        timestamp TEXT
                    )
                """)
                conn.commit()
            print(f"[MEMORY] SQLite system initialized: {self.db_path}")
        except Exception as e:
            print(f"[MEMORY] Init Error: {e}")

    def save(self):
        """No-op for SQLite as we commit per transaction, but kept for API compatibility."""
        pass

    def learn_fact(self, user_text, bot_text):
        """Extracts facts from conversation and stores them in SQLite."""
        u_text = user_text.lower()
        
        now = datetime.now().isoformat()
        learnt = []

        # 1. Names
        if "my name is" in u_text:
            name = user_text.split("is")[-1].strip().strip(".").title()
            if name:
                self._update_fact("user_name", name)
                learnt.append(f"Name: {name}")

        # 2. Preferences
        if "i like" in u_text or "i love" in u_text:
            pref = user_text.split("like")[-1].strip() if "like" in u_text else user_text.split("love")[-1].strip()
            if pref:
                self._add_preference("general", pref)
                learnt.append(f"Preference: {pref}")

        # 3. Location
        if "i am from" in u_text or "i live in" in u_text:
            loc = user_text.split("from")[-1].strip() if "from" in u_text else user_text.split("in")[-1].strip()
            if loc:
                self._update_fact("location", loc.strip(".").title())
                learnt.append(f"Location: {loc}")

        return f"Personality updated: learned {', '.join(learnt)}" if learnt else None

    def _update_fact(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO persistent_facts (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, datetime.now().isoformat())
            )
            conn.commit()

    def _add_preference(self, category: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO preferences (category, content, timestamp) VALUES (?, ?, ?)",
                (category, content, datetime.now().isoformat())
            )
            conn.commit()

    def get_context_prompt(self):
        """Returns context string for LLM injection."""
        prompt = ""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get persistent facts
                cursor = conn.execute("SELECT key, value FROM persistent_facts")
                facts = {row[0]: row[1] for row in cursor.fetchall()}
                
                if "user_name" in facts:
                    prompt += f" The user's name is {facts['user_name']}."
                if "location" in facts:
                    prompt += f" They are from {facts['location']}."

                # Get latest preferences
                cursor = conn.execute("SELECT content FROM preferences ORDER BY id DESC LIMIT 5")
                prefs = [row[0] for row in cursor.fetchall()]
                if prefs:
                    prompt += f" User interests: {', '.join(prefs)}."
        except:
            pass
            
        return prompt
