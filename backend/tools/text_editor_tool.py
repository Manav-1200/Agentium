"""
Text Editor Tool — view, create, str_replace, insert, undo_edit.

Mirrors the behaviour of Claude's built-in text_editor_tool so agents can
edit files on disk with the same predictable, safe semantics.

Safety guarantees
-----------------
- Path traversal blocked (no '..' components)
- Sensitive system paths blocked (/etc, /root, /proc, /sys, /dev, /boot)
- Files larger than MAX_FILE_SIZE_BYTES (10 MB) are rejected
- str_replace fails if old_str occurs 0 or more than once (ambiguous)
- Undo history is capped at MAX_HISTORY_DEPTH snapshots per file (session-scoped)

Tool contract
-------------
TOOL_NAME         : str          — registry key
TOOL_DESCRIPTION  : str          — sent to LLM
AUTHORIZED_TIERS  : list[str]    — tier gate
execute(**kwargs) : async        — single dispatch entry-point
tool_instance     : module-level singleton for ToolFactory.load_tool()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024   # 10 MB
MAX_HISTORY_DEPTH:   int = 20                   # snapshots per file


class TextEditorTool:
    """
    Persistent, undo-aware text file editor for agents.
    """

    TOOL_NAME: str = "text_editor"
    TOOL_DESCRIPTION: str = """
    Persistent text-file editor with session-scoped undo history.

    Actions
    -------
    view       — Read a file with numbered lines; optionally limit to a
                 [start_line, end_line] range (1-based, inclusive).
    create     — Write a new file (or overwrite an existing one) with the
                 given content. Creates parent directories automatically.
    str_replace — Replace a unique string in the file.  Fails if the string
                 appears zero times (not found) or more than once (ambiguous).
    insert     — Insert text before a 1-based line number.
                 Use line 1 to prepend; use line > total_lines to append.
    undo_edit  — Revert the last in-session change to the file.
                 Returns an error if no history exists for the path.
    """
    AUTHORIZED_TIERS: List[str] = ["0xxxx", "1xxxx", "2xxxx", "3xxxx"]

    # Class-level undo history: {absolute_path_str: [snapshot, ...]}
    # Oldest snapshot is index 0; most-recent is index -1.
    _edit_history: ClassVar[Dict[str, List[str]]] = {}

    # ── Blocked path prefixes (security) ──────────────────────────────────────
    _BLOCKED_PREFIXES: ClassVar[tuple] = (
        "/etc", "/root", "/proc", "/sys", "/dev", "/boot",
    )

    # ── Tool contract entry-point ──────────────────────────────────────────────

    async def execute(
        self,
        action:      str,
        path:        str,
        content:     Optional[str] = None,
        old_str:     Optional[str] = None,
        new_str:     Optional[str] = None,
        insert_line: Optional[int] = None,
        insert_text: Optional[str] = None,
        view_range:  Optional[List[int]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Dispatch to the requested editor action."""

        # Validate path before dispatching
        validation = self._validate_path(path)
        if not validation["valid"]:
            return {"success": False, "action": action, "error": validation["error"]}

        abs_path = validation["path"]

        handlers = {
            "view":        lambda: self._view(abs_path, view_range),
            "create":      lambda: self._create(abs_path, content),
            "str_replace": lambda: self._str_replace(abs_path, old_str, new_str),
            "insert":      lambda: self._insert(abs_path, insert_line, insert_text),
            "undo_edit":   lambda: self._undo_edit(abs_path),
        }

        handler = handlers.get(action)
        if not handler:
            return {
                "success": False,
                "action":  action,
                "error":   (
                    f"Unknown action '{action}'. "
                    f"Valid actions: {sorted(handlers.keys())}"
                ),
            }

        try:
            return handler()
        except Exception as exc:
            logger.exception("text_editor action '%s' failed on '%s'", action, path)
            return {"success": False, "action": action, "error": str(exc)}

    # ── Action implementations ─────────────────────────────────────────────────

    def _view(
        self,
        path: Path,
        view_range: Optional[List[int]],
    ) -> Dict[str, Any]:
        if not path.exists():
            return {"success": False, "action": "view",
                    "error": f"File not found: {path}"}
        if not path.is_file():
            return {"success": False, "action": "view",
                    "error": f"Path is not a file: {path}"}

        size = path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            return {"success": False, "action": "view",
                    "error": f"File too large ({size:,} bytes). Limit is {MAX_FILE_SIZE_BYTES:,} bytes."}

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lines)

        if view_range:
            if len(view_range) != 2:
                return {"success": False, "action": "view",
                        "error": "view_range must be [start_line, end_line]"}
            start, end = view_range
            if not (1 <= start <= end <= total):
                return {"success": False, "action": "view",
                        "error": (
                            f"view_range [{start}, {end}] out of bounds "
                            f"(file has {total} lines)"
                        )}
            selected = lines[start - 1 : end]
            numbered = "\n".join(
                f"{i + start:>6}\t{line}"
                for i, line in enumerate(selected)
            )
        else:
            numbered = "\n".join(
                f"{i + 1:>6}\t{line}"
                for i, line in enumerate(lines)
            )

        return {
            "success":    True,
            "action":     "view",
            "path":       str(path),
            "total_lines": total,
            "content":    numbered,
        }

    def _create(self, path: Path, content: Optional[str]) -> Dict[str, Any]:
        if content is None:
            return {"success": False, "action": "create",
                    "error": "'content' is required for create"}

        # Save snapshot if overwriting
        if path.exists() and path.is_file():
            self._push_history(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        return {
            "success": True,
            "action":  "create",
            "path":    str(path),
            "bytes_written": len(content.encode("utf-8")),
        }

    def _str_replace(
        self,
        path:    Path,
        old_str: Optional[str],
        new_str: Optional[str],
    ) -> Dict[str, Any]:
        if old_str is None:
            return {"success": False, "action": "str_replace",
                    "error": "'old_str' is required for str_replace"}
        if new_str is None:
            return {"success": False, "action": "str_replace",
                    "error": "'new_str' is required for str_replace (use '' to delete)"}
        if not path.exists():
            return {"success": False, "action": "str_replace",
                    "error": f"File not found: {path}"}

        original = path.read_text(encoding="utf-8", errors="replace")
        count = original.count(old_str)

        if count == 0:
            return {"success": False, "action": "str_replace",
                    "error": "old_str not found in file — no changes made"}
        if count > 1:
            return {"success": False, "action": "str_replace",
                    "error": (
                        f"old_str appears {count} times in the file — "
                        "must be unique. Add surrounding context to disambiguate."
                    )}

        self._push_history(path, snapshot=original)
        updated = original.replace(old_str, new_str, 1)
        path.write_text(updated, encoding="utf-8")

        return {
            "success":       True,
            "action":        "str_replace",
            "path":          str(path),
            "replaced_with": new_str,
        }

    def _insert(
        self,
        path:        Path,
        insert_line: Optional[int],
        insert_text: Optional[str],
    ) -> Dict[str, Any]:
        if insert_line is None:
            return {"success": False, "action": "insert",
                    "error": "'insert_line' is required for insert"}
        if insert_text is None:
            return {"success": False, "action": "insert",
                    "error": "'insert_text' is required for insert"}
        if not path.exists():
            return {"success": False, "action": "insert",
                    "error": f"File not found: {path}"}
        if insert_line < 1:
            return {"success": False, "action": "insert",
                    "error": "insert_line must be >= 1 (use 1 to prepend)"}

        original = path.read_text(encoding="utf-8", errors="replace")
        self._push_history(path, snapshot=original)

        lines = original.splitlines(keepends=True)
        total = len(lines)

        # Ensure insert_text ends with a newline
        text_to_insert = insert_text if insert_text.endswith("\n") else insert_text + "\n"

        if insert_line == 1:
            lines.insert(0, text_to_insert)
        elif insert_line > total:
            # Append at end — make sure existing last line ends with newline
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(text_to_insert)
        else:
            lines.insert(insert_line - 1, text_to_insert)

        path.write_text("".join(lines), encoding="utf-8")

        return {
            "success":     True,
            "action":      "insert",
            "path":        str(path),
            "inserted_at_line": insert_line,
        }

    def _undo_edit(self, path: Path) -> Dict[str, Any]:
        key = str(path)
        history = self._edit_history.get(key, [])

        if not history:
            return {"success": False, "action": "undo_edit",
                    "error": f"No undo history for: {path}"}

        snapshot = history.pop()
        if not history:
            del self._edit_history[key]

        path.write_text(snapshot, encoding="utf-8")

        return {
            "success":         True,
            "action":          "undo_edit",
            "path":            str(path),
            "remaining_undos": len(history),
        }

    # ── History helpers ────────────────────────────────────────────────────────

    def _push_history(self, path: Path, snapshot: Optional[str] = None) -> None:
        """Save a snapshot of the file before a destructive operation."""
        key = str(path)
        if snapshot is None:
            try:
                snapshot = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return  # Can't read — skip snapshot

        history = self._edit_history.setdefault(key, [])
        history.append(snapshot)
        # Trim oldest entries to stay within cap
        if len(history) > MAX_HISTORY_DEPTH:
            self._edit_history[key] = history[-MAX_HISTORY_DEPTH:]

    # ── Path validation ────────────────────────────────────────────────────────

    def _validate_path(self, path_str: str) -> Dict[str, Any]:
        """
        Resolve and validate a path string.

        Rejects:
        - Empty / non-string input
        - Paths containing '..' traversal components
        - Paths inside blocked system directories
        """
        if not isinstance(path_str, str) or not path_str.strip():
            return {"valid": False, "error": "'path' must be a non-empty string"}

        try:
            resolved = Path(path_str).resolve()
        except Exception as exc:
            return {"valid": False, "error": f"Invalid path: {exc}"}

        # Block traversal attempts
        original_parts = Path(path_str).parts
        if ".." in original_parts:
            return {"valid": False, "error": "Path traversal ('..') is not permitted"}

        # Block sensitive system paths
        resolved_str = str(resolved)
        for blocked in self._BLOCKED_PREFIXES:
            if resolved_str == blocked or resolved_str.startswith(blocked + "/"):
                return {"valid": False,
                        "error": f"Access to '{blocked}' is not permitted"}

        return {"valid": True, "path": resolved}


# ── Module-level singleton ─────────────────────────────────────────────────────
text_editor_tool = TextEditorTool()

# Alias required by ToolFactory.load_tool() dynamic loader
tool_instance = text_editor_tool