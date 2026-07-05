# .claude/hooks — Auto-mode safety guard

`guard_auto_mode.py` is a **PreToolUse** hook wired in `.claude/settings.json`
(matcher `Bash|PowerShell|Write|Edit|NotebookEdit`). It statically inspects each
tool call **before** it runs and decides deny / warn / pass. It **never executes**
the inspected command.

## What it blocks (deny)
1. **.env / API key** — creating/editing `.env`; printing `.env`; printing
   `OPENDART_API_KEY`; writing a real-looking key value into any file; piping the
   key into a file/log. (`.env.example` and `OPENDART_API_KEY` *name* references
   in code are allowed.)
2. **data/raw/** — editing or overwriting existing raw snapshots (verbatim,
   append-only). New snapshot files are allowed.
3. **output/*.xlsx** — overwriting an existing output workbook. New timestamped
   filenames are allowed.
4. **Destructive shell/git** — `rm`/`rm -rf`, `del`, `rmdir`, `rd`,
   `Remove-Item`, `git reset`, `git clean`, `git checkout -- .` / `git checkout .`,
   `git restore`, `find -delete`, `find -exec rm`.

## What it warns on (non-blocking)
5. **Source traceability** — an `Edit` to `src/parse.py|accounts.py|collect.py|ratios.py`
   whose diff removes a source-reference token (`request_hash`, `rcept_no`,
   `retrieved_at`, `account_id`) emits a reminder but does not block.

## What it always allows (pass)
`dir`/`ls`/`Get-ChildItem`, `cat`/`type`/`Get-Content` on normal docs,
`mkdir`/`New-Item`, `python -m pytest`, `python -m src.pipeline`,
`git status`, `git diff`, and creating any new (non-existing) file, including new
docs and new `data/raw/` snapshots.

## Behavior notes
- **Fails open**: if Python is missing or the script errors, the tool proceeds
  (the guard never locks you out). It is a safety net, not a hard sandbox.
- Requires `python` (falls back to `py`) on PATH.
- Reasons print in the permission prompt so you can see *why* something is blocked.

## Managing the hook
- Review/disable via the `/hooks` menu, or edit `.claude/settings.json`.
- After first adding/editing hooks, open `/hooks` once (or restart) so the
  settings watcher reloads them.
- Validate the script statically (no live danger) by piping a synthetic event:
  `python .claude/hooks/guard_auto_mode.py < event.json`
