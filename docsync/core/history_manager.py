"""
History Manager Module

Manages version history with JSON file storage and PDF backup.
Extracted from HistoryManager in app_main.py.
"""

import os
import json
import shutil
import logging
from typing import List, Dict, Optional
from datetime import datetime

from docsync.models import ProcessingResult

logger = logging.getLogger("docsync.history_manager")


class HistoryManager:
    """
    Manages document version history.
    
    Stores: original PDF paths, backup copies, processing results,
    timestamps, and change metadata for rollback support.
    """

    def __init__(self, storage_dir: str = "./data/history", max_versions: int = 50):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.history_file = os.path.join(storage_dir, "history.json")
        self.history = self._load_history()
        self.max_versions = max_versions

    def _load_history(self) -> Dict:
        """Load history from JSON file (handles legacy list format)"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    data = json.load(f)
                # Handle legacy format: plain list → wrap in dict
                if isinstance(data, list):
                    return {"versions": data}
                if isinstance(data, dict) and "versions" in data:
                    return data
                return {"versions": []}
            except Exception:
                return {"versions": []}
        return {"versions": []}

    def _save_history(self):
        """Persist history to JSON file"""
        with open(self.history_file, "w") as f:
            json.dump(self.history, f, indent=2, default=str)

    def add_version(
        self,
        pdf_path: str,
        changes: Dict,
        result: Optional[ProcessingResult] = None,
    ) -> Dict:
        """
        Record a new version entry.
        
        Creates a backup of the original PDF and stores metadata
        about what changed.
        """
        version_id = len(self.history.get("versions", [])) + 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Backup the original PDF
        backup_path = None
        if os.path.exists(pdf_path):
            backup_dir = os.path.join(self.storage_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_filename = f"v{version_id}_{os.path.basename(pdf_path)}"
            backup_path = os.path.join(backup_dir, backup_filename)
            shutil.copy2(pdf_path, backup_path)

        version_entry = {
            "version_id": version_id,
            "timestamp": timestamp,
            "original_pdf": pdf_path,
            "backup_path": backup_path,
            "changes": changes,
            "result": {
                "success": result.success if result else False,
                "images_replaced": result.images_replaced if result else 0,
                "text_replaced": result.text_replaced if result else 0,
                "confidence": result.overall_confidence if result else 0,
                "processing_time": result.processing_time if result else 0,
                "output_path": result.output_path if result else "",
            },
        }

        if "versions" not in self.history:
            self.history["versions"] = []

        self.history["versions"].append(version_entry)

        # Enforce max versions
        if len(self.history["versions"]) > self.max_versions:
            removed = self.history["versions"].pop(0)
            # Remove old backup file
            old_backup = removed.get("backup_path")
            if old_backup and os.path.exists(old_backup):
                try:
                    os.remove(old_backup)
                except Exception:
                    pass

        self._save_history()
        logger.info(f"Version {version_id} recorded for {os.path.basename(pdf_path)}")
        return version_entry

    def get_history(self) -> List[Dict]:
        """Get all version history entries"""
        return self.history.get("versions", [])

    def get_version(self, version_id: int) -> Optional[Dict]:
        """Get a specific version entry by ID"""
        for v in self.history.get("versions", []):
            if v.get("version_id") == version_id:
                return v
        return None

    def rollback(self, version_id: int) -> Optional[str]:
        """
        Rollback to a specific version.
        Returns the backup PDF path, or None if version not found.
        """
        version = self.get_version(version_id)
        if version is None:
            logger.warning(f"Version {version_id} not found")
            return None

        backup_path = version.get("backup_path")
        if backup_path and os.path.exists(backup_path):
            # Restore the backup to the original location
            original = version.get("original_pdf")
            if original:
                shutil.copy2(backup_path, original)
                logger.info(f"Rolled back to version {version_id}: {original}")
                return original

        logger.warning(f"Backup file not found for version {version_id}")
        return None

    def get_formatted_history(self) -> str:
        """Get a human-readable history summary"""
        versions = self.get_history()
        if not versions:
            return "No version history available."

        lines = ["Version History", "=" * 50]
        for v in versions:
            res = v.get("result", {})
            lines.append(
                f"  v{v['version_id']} | {v['timestamp']} | "
                f"Images: {res.get('images_replaced', 0)} | "
                f"Text: {res.get('text_replaced', 0)} | "
                f"Confidence: {res.get('confidence', 0):.0%}"
            )
        return "\n".join(lines)
