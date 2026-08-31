# QR-Trends — Agent Instructions

This repo is built around the **WAT framework** (Workflows, Agents, Tools). Full
rationale and architecture: [`docs/PRD.md`](docs/PRD.md).

## How to operate

1. **Look for existing tools first.** Before writing a new script, check `tools/` for
   something that already does the job. Only create a new one when nothing exists for
   that task.
2. **Read the workflow before acting.** If a task matches an existing SOP in
   `workflows/`, read it, gather the inputs it calls for, then run the matching
   tool(s) — don't improvise the equivalent of a workflow ad hoc.
3. **When something fails:**
   - Read the full error/trace before guessing at a fix.
   - Fix the script and retest — check in before retrying anything that costs money or
     API credits.
   - Update the relevant workflow with what was learned (rate limits, timing quirks,
     unexpected behavior) so the failure doesn't recur.
4. **Keep workflows current, but don't overwrite them casually.** They're agreed
   process, not scratch notes — update them as better methods are found, but don't
   create or overwrite one without checking first unless explicitly told to.
5. **Secrets go in `.env` only** (gitignored). Never hardcode credentials or put them
   anywhere else. `credentials.json` / `token.json` (OAuth artifacts) are gitignored
   for the same reason.
6. **`.tmp/` is disposable.** Intermediate/scratch files go there and can be
   regenerated at any time — never treat it as a source of truth. Real outputs surface
   in the web dashboard (see `docs/PRD.md` — Phase 3, not yet built).

## Project status

Foundation phase only — the WAT scaffold exists but the QR-Trends product scope is not
yet defined. See `docs/PRD.md` for the roadmap and open questions. Don't assume
product requirements that aren't written there.
