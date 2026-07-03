"""Filesystem MCP adapter constrained to the configured learning-data root."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.config import COACH_DATA_DIR


class FilesystemMCPClient:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or COACH_DATA_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("filesystem MCP path escapes the configured data root")
        return candidate

    def read_json(self, relative_path: str, default: Any = None) -> Any:
        path = self._safe_path(relative_path)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def write_json(self, relative_path: str, value: Any) -> str:
        path = self._safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)
        return str(path)

    def list_json(self, relative_dir: str) -> list[dict[str, Any]]:
        directory = self._safe_path(relative_dir)
        if not directory.exists() or not directory.is_dir():
            return []
        items: list[dict[str, Any]] = []
        for path in directory.glob("*.json"):
            value = self.read_json(str(path.relative_to(self.root)), default=None)
            if isinstance(value, dict):
                items.append({
                    "path": str(path.relative_to(self.root)),
                    "mtime": path.stat().st_mtime,
                    "content": value,
                })
        return sorted(items, key=lambda item: float(item["mtime"]), reverse=True)


__all__ = ["FilesystemMCPClient"]
