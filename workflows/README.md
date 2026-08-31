# Workflows

Markdown SOPs live here — one file per task the agent needs to perform. Each workflow
should define:

- **Objective** — what this workflow accomplishes
- **Required inputs** — what the agent needs before starting
- **Tools used** — which script(s) in `tools/` to call, and in what order
- **Expected outputs** — what "done" looks like
- **Edge cases** — known failure modes and how to handle them

Written in plain language, the way you'd brief a teammate. See `../docs/PRD.md` for the
full WAT architecture this convention is part of.

This directory is currently empty — workflows will be added once the QR-Trends product
scope is defined.
