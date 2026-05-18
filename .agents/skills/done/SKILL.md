---
name: done
description: Capture session decisions, open questions, follow-ups, and handoff context. Use when the user asks to wrap up a substantive session or mentions `/done`.
---

# Session Capture

Use this skill only for substantive work sessions. If the session was just a quick lookup or greeting, report that there is nothing worth capturing.

## Workflow

1. Review the current conversation and identify:
   - session topic
   - project name
   - decisions made
   - open questions
   - follow-up actions
   - important artifacts created or modified
2. Update `dev/session-log.md`.
   - Create the file if needed with a short header.
   - Insert the new entry at the top.
3. Write a condensed handoff file to `dev/chats/<project-name>_<YYYY-MM-DD>_<HH-MM>_handoff.md`.
4. Move entries older than 60 days from `dev/session-log.md` to `dev/session-log-archive.md`.
5. Append a line to `dev/skill-performance.csv` describing the capture run.

## Entry format

Include:

- Project(s)
- Duration
- Decisions
- Open Questions
- Follow-ups
- Artifacts
- Context

## Output

Confirm what was captured, where it was written, and the most important next follow-up.

