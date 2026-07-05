#!/usr/bin/env python3
"""Minimal Auto-mode safety guard (PreToolUse hook).

Reads a Claude Code PreToolUse event on stdin and decides deny / warn / pass.
Conservative and STATIC: it never executes the inspected command. It blocks
clearly dangerous actions, warns (non-blocking) on traceability risks, and
stays silent for normal development (new files, docs, tests, pipeline runs).

Scope for the OpenDART anomaly project:
  1) .env / OPENDART_API_KEY exposure
  2) data/raw/ overwrite & delete protection (append-only audit layer)
  3) output/*.xlsx overwrite protection (no silent clobber)
  4) destructive shell / git commands
  5) source-traceability warning (non-blocking)

Fails OPEN: any unexpected error -> pass (never lock the developer out).
Output uses ASCII-safe JSON (ensure_ascii) so Windows code pages can't crash it.
"""

import json
import os
import re
import sys

SOURCE_REF_TOKENS = ("request_hash", "rcept_no", "retrieved_at", "account_id")
TRACE_SENSITIVE = ("src/parse.py", "src/accounts.py", "src/collect.py", "src/ratios.py")
KEY_PLACEHOLDERS = {
    "", "your_key", "your_api_key", "yourkey", "changeme", "change_me",
    "xxx", "...", "placeholder", "todo", "none", "null", "dummy",
}


def emit(decision=None, reason=None, system_message=None):
    """Print a PreToolUse decision (ASCII-safe) and exit 0."""
    payload = {}
    if decision:
        payload["hookSpecificOutput"] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason or "",
        }
    if system_message:
        payload["systemMessage"] = system_message
    if payload:
        sys.stdout.write(json.dumps(payload))  # ensure_ascii=True by default
    sys.exit(0)


def project_root():
    return os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def abspath(path):
    if os.path.isabs(path):
        return os.path.realpath(path)
    return os.path.realpath(os.path.join(project_root(), path))


def relpath(path):
    try:
        rel = os.path.relpath(abspath(path), project_root())
    except Exception:
        return None
    if rel.startswith(".."):
        return None
    return rel.replace("\\", "/")


def looks_like_real_key(text):
    """True if text assigns OPENDART_API_KEY a value that looks like a real key."""
    if not text:
        return False
    for m in re.finditer(r"OPENDART_API_KEY\s*[=:]\s*[\"']?([^\s\"'#]+)", text, re.I):
        val = m.group(1).strip()
        low = val.lower()
        if low in KEY_PLACEHOLDERS:
            continue
        if val[0] in "<$":                       # ${VAR} / <your_key> / $VAR reference
            continue
        if "your" in low or "example" in low or "placeholder" in low:
            continue
        if len(val) >= 16:                       # long opaque token -> likely a real key
            return True
    return False


def check_file(tool, ti):
    path = ti.get("file_path", "") or ""
    if not path:
        emit()
    base = os.path.basename(path.replace("\\", "/"))
    rel = relpath(path)
    content = ti.get("new_string", "") if tool == "Edit" else ti.get("content", "")

    # 1) .env protection (allow .env.example)
    if base == ".env":
        emit("deny", ".env is protected. Manage the real key only in .env (git-ignored). .env.example is allowed.")
    if looks_like_real_key(content):
        emit("deny", "Refusing to write what looks like a real OPENDART_API_KEY value into a file. Only placeholders are allowed.")

    if rel:
        exists = os.path.exists(abspath(path))
        # 2) data/raw protection
        if rel.startswith("data/raw/") and base != ".gitkeep":
            if tool == "Edit":
                emit("deny", "data/raw/ is a verbatim append-only audit layer. Editing existing raw snapshots is blocked.")
            if exists:
                emit("deny", "Overwriting an existing file under data/raw/ is blocked. Save a new snapshot under a new filename.")
        # 3) output/*.xlsx overwrite protection
        if rel.startswith("output/") and rel.lower().endswith(".xlsx") and exists:
            emit("deny", "Overwriting an existing output .xlsx is blocked. Write a new timestamped filename (atomic replace).")
        # 5) traceability warning (non-blocking, Edit diff only)
        if rel in TRACE_SENSITIVE and tool == "Edit":
            old = ti.get("old_string", "") or ""
            new = ti.get("new_string", "") or ""
            dropped = [t for t in SOURCE_REF_TOKENS if t in old and t not in new]
            if dropped:
                emit(system_message="[traceability warning] " + rel
                     + ": source-reference field(s) removed: " + ", ".join(dropped)
                     + ". Keep FinancialFact/parsed rows traceable to source.")
    emit()


# (regex, human name) — matched case-insensitively against the command string.
DENY_CMD = [
    (r"(?:^|[\n;&|]\s*)rm(?:\s|$)", "rm"),
    (r"\brm\s+-[a-z]*r", "rm -r"),
    (r"(?:^|[\n;&|]\s*)del(?:\s|$)", "del"),
    (r"(?:^|[\n;&|]\s*)rmdir(?:\s|$)", "rmdir"),
    (r"(?:^|[\n;&|]\s*)rd(?:\s|$)", "rd"),
    (r"\bRemove-Item\b", "Remove-Item"),
    (r"\bgit\s+reset\b", "git reset"),
    (r"\bgit\s+clean\b", "git clean"),
    (r"\bgit\s+checkout\b(?=.*(?:\s--(?:\s|$)|\s\.\s*$))", "git checkout (discard)"),
    (r"\bgit\s+restore\b", "git restore"),
    (r"\bfind\b.*-delete\b", "find -delete"),
    (r"\bfind\b.*-exec\s+rm", "find -exec rm"),
]


def check_command(cmd):
    c = (cmd or "").strip()
    if not c:
        emit()

    # 1) .env / key exposure
    if re.search(r"(?:cat|type|bat|less|more|head|tail|nl|Get-Content|gc)\b[^\n]*\.env\b", c, re.I) \
            and not re.search(r"\.env\.example", c, re.I):
        emit("deny", "Printing .env contents is blocked. (.env.example is allowed.)")
    if re.search(r"(?:echo|print|printenv|write-host|write-output)\b[^\n]*OPENDART_API_KEY", c, re.I):
        emit("deny", "Printing the OPENDART_API_KEY value to the screen is blocked.")
    if re.search(r"OPENDART_API_KEY", c) and re.search(r"(>>?|\btee\b|Out-File|Set-Content|Add-Content)", c, re.I):
        emit("deny", "Command may leak the API key into a file/log. Blocked.")

    # 4) destructive shell / git
    for pat, name in DENY_CMD:
        if re.search(pat, c, re.I):
            emit("deny", "Destructive/undo command ('" + name + "') is blocked in Auto mode. Run it manually if truly intended.")

    emit()


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        emit()  # cannot parse -> do not interfere
    try:
        tool = event.get("tool_name", "")
        ti = event.get("tool_input", {}) or {}
        if tool in ("Write", "Edit", "NotebookEdit"):
            check_file(tool, ti)
        elif tool in ("Bash", "PowerShell"):
            check_command(ti.get("command", ""))
    except SystemExit:
        raise
    except Exception:
        emit()  # fail open on any unexpected error
    emit()


if __name__ == "__main__":
    main()
