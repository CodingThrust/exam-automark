---
name: setup-zulip-grading
description: Use when an instructor wants to wire up Zulip-based homework submission for the course — creates a grading bot on the instructor's Zulip realm via API, writes `.zuliprc` at repo root, and bootstraps `coursedesign/roster.csv`. Run once after `/bootstrap`. Triggers on phrases like "set up zulip submissions", "configure zulip grading bot", "wire up the homework bot", "/setup-zulip-grading".
---

# setup-zulip-grading

One-time setup that creates a course-specific Zulip bot, writes its credentials to `.zuliprc` (gitignored), and seeds the student roster. After this runs, students can DM the bot with homework photos and the instructor can run `/zulip-mark-feedback N` to grade.

## When to use

- After `/bootstrap` has written `config.toml`.
- Course is using Zulip for homework submission.
- `.zuliprc` does not yet exist at repo root (or the instructor wants to rebuild the roster).

Do NOT use for: production-grade bot deployment, multi-realm bots, or replacing an existing bot in a different repo.

## What this skill produces

- `.zuliprc` at repo root (gitignored) — Zulip API credentials for the grading bot.
- `coursedesign/roster.csv` (committed) — Zulip-email → student-id → student-name mapping.
- A student-facing one-liner the instructor can paste into the course Zulip channel.

## Prerequisites

- `/bootstrap` already run (i.e., `config.toml` exists with a real `course-code`).
- `uv` available (used to run the scripts with the `zulip` Python package).
- Instructor has a Zulip account on the realm they want to use.

## Workflow

### Step 1 — Verify prerequisites

```bash
test -f config.toml || { echo "MISSING: run /bootstrap first"; exit 1; }
command -v uv >/dev/null || { echo "MISSING: uv"; exit 1; }
```

Read `course-code` from `config.toml` — this becomes part of the bot's full name and short name.

### Step 2 — Handle existing `.zuliprc`

If `.zuliprc` already exists, verify it first:

```bash
uv run python .claude/skills/setup-zulip-grading/scripts/verify.py --config .zuliprc
```

- Exit 0 → bot already works. Jump to Step 5 (roster) and offer to rebuild only the roster.
- Exit 1/2 → invalid or stale credentials. Ask the user via `AskUserQuestion` whether to (A) recreate the bot, or (B) abort and fix manually.

### Step 3 — Walk the instructor through getting their personal API key

Print this verbatim:

> 1. Open your Zulip realm in a browser (e.g., `https://yourorg.zulipchat.com`).
> 2. Click your avatar → **Personal settings** → **Account & privacy**.
> 3. Next to **API key**, click **Show/change your API key**.
> 4. Enter your Zulip password when prompted.
> 5. Copy the API key shown on screen.

Then ask via `AskUserQuestion` for three values (separately, for clarity):
- Realm URL (e.g., `https://yourorg.zulipchat.com`)
- Login email
- API key

**Do not echo the API key back into chat.** Pass it to the script via the `ZULIP_API_KEY` env var, not as a command-line argument (process listings can leak args).

### Step 4 — Create the bot

```bash
ZULIP_API_KEY="<pasted>" uv run python .claude/skills/setup-zulip-grading/scripts/create_bot.py \
  --site "<realm_url>" \
  --instructor-email "<email>" \
  --course-code "<course-code from config.toml>" \
  --out .zuliprc
```

The script prints a JSON line with the new bot's identity on stdout, e.g.:

```json
{"email": "dsaa3071-grading-bot@yourorg.zulipchat.com", "user_id": 1234, "full_name": "DSAA3071 grading bot"}
```

**Exit-code handling:**

| Exit code | Meaning | Action |
|-----------|---------|--------|
| 0 | Bot created, `.zuliprc` written | Continue to Step 5 |
| 2 | Realm forbids bot creation by non-admins | Fall back to manual UI walk-through (Step 4b) |
| 3 | A bot with that short_name already exists | Ask the user via `AskUserQuestion`: reuse (download its zuliprc manually) or pick a different short_name |
| 4 | Other API error | Show stderr to user; abort |

If `.zuliprc` is not already in `.gitignore`, append it.

#### Step 4b — Manual fallback (only on exit 2)

Print this verbatim:

> Your realm restricts who can create bots. Create the bot manually:
> 1. Zulip → ⚙️ → **Personal settings** → **Bots** → **Add a new bot**.
> 2. Type: **Generic bot**. Full name: **`<course-code> grading bot`**. Short name: **`<course>-grading`**.
> 3. After it's created, click the bot → **Download zuliprc**.
> 4. Paste the path to the downloaded file here.

Then `cp <downloaded_path> .zuliprc`, and run `verify.py` to confirm.

### Step 5 — Build the roster

Ask via `AskUserQuestion` how to seed `coursedesign/roster.csv`:

- **A:** "Paste a CSV/TSV block with columns `zulip_email,student_id,student_name`" — accept the block, validate (three columns, no duplicate emails), write the file.
- **B:** "Start empty — I'll add students as they DM the bot for the first time" — write a header-only file:
  ```csv
  zulip_email,student_id,student_name
  ```

The roster is the **only** join between Zulip identity and `student_id` (the canonical key used in `grades.csv` and `<student_id>_...` filenames). It's committed to git — no secrets inside.

### Step 6 — Print the student onboarding one-liner

Show the instructor a ready-to-paste announcement, substituting the bot's `full_name` from Step 4's JSON:

> "📚 **Homework submission via Zulip**: DM the bot **@<bot full name>** with photos of your work before each homework deadline. Make sure the email on your Zulip account matches the one on the class roster. You'll get per-question feedback by DM after grading."

### Step 7 — Wrap up

Run `verify.py` one more time and print the bot's profile. Tell the instructor:

> Setup complete. Next steps:
> - Paste the announcement above into your course Zulip channel.
> - When the homework deadline passes, run `/zulip-mark-feedback N` to pull, grade, and send feedback.

## Failure modes

- **Realm forbids bot creation** → fallback to manual UI walk-through (Step 4b). Common in tightly-locked-down workplace realms.
- **Bot short_name collision** (e.g., re-running setup after an aborted attempt) → script exits 3; ask user whether to pick a new short_name or reuse the existing bot (manual zuliprc download).
- **API key copied wrong** (whitespace, truncated) → `create_bot.py` returns a clear "401 Unauthorized" via stderr; ask user to re-paste.
- **Realm URL has trailing slash** or missing protocol → script normalizes both; if it still fails, surface the error.
- **`config.toml` missing `course-code`** (placeholder still `<Course Code>`) → ask user to either run `/bootstrap` to fix it or pass `--course-code` explicitly.

## Idempotency

Safe to re-run. If `.zuliprc` exists and works, Step 4 is skipped and only the roster + announcement steps re-run. If `.zuliprc` exists but is broken, the script can recreate the bot (user confirmation required first).
