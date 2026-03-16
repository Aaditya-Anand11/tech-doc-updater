"""
DocSync RBAC Module

Role-Based Access Control with SQLite backend.
Supports three roles: viewer, editor, admin.
"""

import os
import hashlib
import secrets
import sqlite3
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger("docsync.auth")


class Role:
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


# Permissions mapping
# viewer  – can only view logs and the dashboard
# editor  – can run the core processing software
# admin   – full access including database add/remove
ROLE_PERMISSIONS = {
    Role.VIEWER: {"view_logs", "view_dashboard"},
    Role.EDITOR: {
        "view_logs", "view_dashboard",
        "process_document", "compare_images", "view_history", "rollback",
    },
    Role.ADMIN: {
        "view_logs", "view_dashboard",
        "process_document", "compare_images", "view_history", "rollback",
        "manage_users", "manage_plugins", "manage_config",
        "manage_db",
    },
}


def _hash_password(password: str, salt: str = None) -> tuple:
    """Hash a password with a salt"""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt


class RBACManager:
    """
    Role-Based Access Control Manager with SQLite storage.
    
    Default admin account created on first run:
        username: admin
        password: admin123  (should be changed)
    """

    def __init__(self, db_path: str = "./data/docsync.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with users table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                created_at TEXT NOT NULL,
                last_login TEXT,
                active INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        # Create default users if no users exist
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            now = datetime.now().isoformat()
            for uname, pwd, role in [
                ("admin", "admin123", Role.ADMIN),
                ("editor", "editor123", Role.EDITOR),
                ("viewer", "viewer123", Role.VIEWER),
            ]:
                hashed, salt = _hash_password(pwd)
                cursor.execute(
                    "INSERT INTO users (username, password_hash, salt, role, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (uname, hashed, salt, role, now),
                )
            logger.info("Default accounts created: admin, editor, viewer")

        conn.commit()
        conn.close()

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        Authenticate a user. Returns user info dict or None.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username, password_hash, salt, role, active FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()

        if row is None:
            conn.close()
            return None

        user_id, uname, stored_hash, salt, role, active = row

        if not active:
            conn.close()
            return None

        hashed, _ = _hash_password(password, salt)
        if hashed != stored_hash:
            conn.close()
            return None

        # Update last login
        cursor.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(), user_id),
        )
        conn.commit()
        conn.close()

        self._log_audit(username, "login", "Successful authentication")

        return {"id": user_id, "username": uname, "role": role}

    def authorize(self, user: Dict, permission: str) -> bool:
        """Check if a user has a specific permission"""
        role = user.get("role", Role.VIEWER)
        return permission in ROLE_PERMISSIONS.get(role, set())

    def create_user(self, username: str, password: str, role: str = Role.VIEWER) -> bool:
        """Create a new user"""
        if role not in (Role.VIEWER, Role.EDITOR, Role.ADMIN):
            return False
        if not username or not username.strip():
            return False
        if not password or len(password.strip()) < 4:
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            hashed, salt = _hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash, salt, role, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, hashed, salt, role, datetime.now().isoformat()),
            )
            conn.commit()
            logger.info(f"User created: {username} (role: {role})")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"User already exists: {username}")
            return False
        finally:
            conn.close()

    def list_users(self) -> List[Dict]:
        """List all users (without passwords)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username, role, created_at, last_login, active FROM users"
        )
        users = []
        for row in cursor.fetchall():
            users.append({
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "created_at": row[3],
                "last_login": row[4],
                "active": bool(row[5]),
            })
        conn.close()
        return users

    def update_role(self, username: str, new_role: str) -> bool:
        """Update a user's role"""
        if new_role not in (Role.VIEWER, Role.EDITOR, Role.ADMIN):
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (new_role, username),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def deactivate_user(self, username: str) -> bool:
        """Deactivate a user account"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET active = 0 WHERE username = ?",
            (username,),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def _log_audit(self, username: str, action: str, details: str = ""):
        """Log an audit event"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_log (username, action, details, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (username, action, details, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """Retrieve recent audit log entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, action, details, timestamp FROM audit_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        entries = [
            {"username": r[0], "action": r[1], "details": r[2], "timestamp": r[3]}
            for r in cursor.fetchall()
        ]
        conn.close()
        return entries

    # ── Database Management (admin) ──────────────────────

    def reset_database(self):
        """Drop all tables and re-initialise the database (admin only)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS audit_log")
        cursor.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        conn.close()
        self._init_db()
        logger.info("Database reset completed – default users recreated")
        return True

    def get_db_info(self) -> Dict:
        """Return summary information about all database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]
        info = {"db_path": self.db_path, "tables": {}}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
            count = cursor.fetchone()[0]
            cursor.execute(f"PRAGMA table_info([{table}])")
            columns = [r[1] for r in cursor.fetchall()]
            info["tables"][table] = {"row_count": count, "columns": columns}
        conn.close()
        return info
