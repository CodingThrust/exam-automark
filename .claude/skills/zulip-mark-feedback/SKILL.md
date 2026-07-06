---
name: zulip-mark-feedback
description: Use when an instructor wants to pull homework photos that students DM'd to the grading bot, grade them, and DM per-question feedback back. End-to-end Zulip-based grading orchestrator that delegates to /grade-homework and (optionally) /homework-report. Requires /setup-zulip-grading to have been run once. Triggers on phrases like "grade homework via zulip", "pull and mark week N from zulip", "/zulip-mark-feedback 3", "send the feedback DMs".
---

# zulip-mark-feedback

Per-homework orchestrator. Four phases with checkpoints between each so the instructor stays in control:

1. **Pull** — Zulip DMs → `weekN/submissions/`
2. **Grade** — delegate to `/grade-homework`
3. **Report** — delegate to `/homework-report` (optional)
4. **Send** — DM per-student feedback files back via the bot

## When to use

- `/setup-zulip-grading` has been run (`.zuliprc` exists at repo root, `coursedesign/roster.csv` exists).
- A homework deadline has passed and students have DM'd photos to the bot.
- You want a single command that runs the whole loop with checkpoints.

Do NOT use for:

- Initial bot setup (use `/setup-zulip-grading`).
- Grading files that students didn't submit via Zulip (use `/grade-homework` directly).
- Sending arbitrary announcements via the bot.

## What this skill produces

- `weekN/submissions/<student_id>_<msgid>_<n>_<orig>.<ext>` — pulled attachments (filename convention matches `/grade-homework`).
- `weekN/submissions/_unknown/...` — attachments from senders not in `roster.csv`.
- `weekN/grades/grades.csv` and `weekN/grades/feedback/<student_id>.md` — produced by the delegated `/grade-homework` run.
- `weekN/grades/report/grading_report.pdf` — if Phase 3 was run.
- DMs to each student with their feedback markdown.
- `weekN/zulip-pull.json`, `weekN/zulip-feedback-sent.json` — gitignored state for idempotent re-runs.

## Inputs

- `N` (required) — homework week number.
- Optional `--since YYYY-MM-DD[THH:MM]`, `--until ...` to override the active window. Default is "everything received since the last pull."
- Optional `--resend` to re-DM feedback to students already in the sent state.

## Workflow

### Step 0 — Prereq check

```bash
test -f .zuliprc || { echo "MISSING: run /setup-zulip-grading first"; exit 1; }
test -f coursedesign/roster.csv || { echo "MISSING: run /setup-zulip-grading first"; exit 1; }
```

### Step 1 — Phase 1: Pull from Zulip

If `weekN/zulip-pull.json` exists, the script uses its `last_message_id` as the anchor for an incremental pull. Otherwise, ask the user via `AskUserQuestion` for `--since` and (optionally) `--until` for the active homework window.

```bash
uv run python .claude/skills/zulip-mark-feedback/scripts/pull_submissions.py \
  --week N \
  [--since 2026-05-15T00:00] \
  [--until 2026-05-22T23:59]
```

Parse the JSON summary on stdout:

```json
{
  "week": 3,
  "messages_seen": 47,
  "files_written": 38,
  "students": {"20240001": 2, "20240002": 3, ...},
  "unknowns": [{"sender_email": "carol@example.edu", "sender_name": "Carol Lee", "files": 1}],
  "submissions_dir": "week3/submissions",
  "state_path": "week3/zulip-pull.json"
}
```

**If `unknowns` is non-empty**, present each one to the user via `AskUserQuestion`:

- **A:** "Add to roster as `<student_id>,<student_name>`" — append the row to `coursedesign/roster.csv` and move files from `_unknown/<msgid>_*` to `<student_id>_<msgid>_*` at the top of `submissions/`.
- **B:** "Skip — leave files in `_unknown/` for manual handling."
- **C:** "Cancel grading and abort."

After resolving unknowns, **checkpoint**: print the per-student file count and ask "proceed to grading? (y/n)".

### Step 2 — Phase 2: Grade (delegate)

Invoke the existing `/grade-homework` skill via the Skill tool with the working directory set to `weekN/submissions/`. The grader produces `weekN/grades/grades.csv` and `weekN/grades/feedback/<student_id>.md` exactly as it would for any local submission folder.

Note for the grader: the solutions doc must be discoverable in or near `weekN/submissions/` — instructors typically drop their `solutions.pdf` there before running this skill. If `/grade-homework` reports `solutions_error`, surface it and stop.

**Checkpoint**: after grading completes, show the score summary (count of students, mean, flagged items count) and ask "build the PDF report? (y/n)".

### Step 3 — Phase 3: Report (delegate, optional)

If yes, invoke the existing `/homework-report` skill. Produces `weekN/grades/report/grading_report.pdf`.

**Checkpoint**: ask "DM feedback to students? (y/n) — default is no; review the feedback markdown files locally first."

### Step 4 — Phase 4: Send feedback DMs

This is the gate that's visible to students. Default behavior: instructor reviews `weekN/grades/feedback/*.md` locally first, then explicitly confirms.

**Recommended interaction**:

1. List the feedback files; offer a `--dry-run` first:

   ```bash
   uv run python .claude/skills/zulip-mark-feedback/scripts/send_feedback.py \
     --week N --dry-run
   ```

   Parse the JSON summary; show counts (sent / skipped / failed). Any `skipped` entries with reason `no_roster_email` mean the roster is incomplete — go fix it, then re-run dry-run.

2. Read the first feedback file inline and show it to the instructor as a preview. Ask via `AskUserQuestion`:
   - **A:** "Send all (already reviewed all files locally)"
   - **B:** "Send only specific students — paste comma-separated `<student_id>` list"
   - **C:** "Cancel"

3. Execute the chosen action:

   ```bash
   # Option A — send all
   uv run python .claude/skills/zulip-mark-feedback/scripts/send_feedback.py --week N

   # Option B — restricted set
   uv run python .claude/skills/zulip-mark-feedback/scripts/send_feedback.py \
     --week N --student-ids 20240001,20240002,20240007
   ```

4. Parse the JSON summary, surface the final counts:

   ```
   Phase 4 done — sent: 38, skipped: 1 (no_roster_email), failed: 0.
   ```

   If `failed` is non-empty, show each entry's reason to the user.

### Step 5 — Wrap up

Print the locations of everything that was produced (`weekN/grades/grades.csv`, the report PDF, the sent-state JSON), and remind the instructor that they can:

- Re-run with `--resend` to re-DM specific students after fixing feedback markdown.
- Re-run with a fresh `--since` window if students submit late.

## Failure modes

- **`.zuliprc` missing or stale** — Step 0 catches it; tell user to run `/setup-zulip-grading`.
- **Roster has no entry for sender** — written to `_unknown/`; interactive prompt at end of Phase 1.
- **Attachment download fails (transient network)** — `pull_submissions.py` logs a warn line and continues with other attachments; the partial files for the failed message are absent and will be retried on next pull (the message ID will not be in `last_message_id` until any download succeeds for it, but already-downloaded attachments for the same message are not re-fetched because their filenames embed the message ID).
- **No new messages in window** — `files_written: 0`; ask user whether they want to grade what's already in `weekN/submissions/` (still useful if a previous pull populated it) or stop.
- **Solutions doc missing in Phase 2** — `/grade-homework` surfaces this; stop and ask user to drop a solutions file in `weekN/`.
- **`send_feedback.py` partial failure** (e.g., one student's email bounced) — the `sent` list in the state file only records successful sends; re-run is safe and resumes from the failure point.
- **Feedback message exceeds 10K chars** — `send_feedback.py` splits on paragraph boundaries; if a single paragraph still exceeds the limit, it splits on character boundary (rare for typical per-question feedback).
- **Student DM'd text only, no attachment** — silently filtered out at Phase 1 (text DMs are common; students may ask questions). The script counts them in `messages_seen` minus files-attributed messages, so an instructor can spot-check.

## Idempotency

Re-running the whole skill is safe at any point:

- **Phase 1**: state file's `last_message_id` ensures already-pulled messages aren't double-fetched. Attachments with the same `<msgid>_<n>` filename simply overwrite (same content).
- **Phase 2**: `/grade-homework`'s own recovery logic (`write_outputs.py` skips students already in `grades.csv`).
- **Phase 4**: `zulip-feedback-sent.json` tracks per-student sent state; default skip already-sent.

Pass `--resend` to force-resend feedback (useful after editing a feedback file).
