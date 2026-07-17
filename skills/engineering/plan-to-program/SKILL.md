---
name: plan-to-program
description: Turn a concluded plan discussion into an issue-tracker program — parent spec, ratified decision register, blocked child tickets, plus implementation and adversarial-review prompts posted on the parent.
disable-model-invocation: true
---

# /plan-to-program

Turn the plan agreed in this conversation into a GitHub issue program — parent spec,
ratified decision register, blocked child tickets — plus an implementation prompt and an
adversarial review prompt posted on the parent.

Input: the current conversation (a concluded plan discussion). Tracker: GitHub via `gh`;
triage label `ready-for-agent`. Do not re-open decisions the conversation already settled.
This command ends when the issues and prompts are published — never launch an
implementation or review session yourself.

## Instructions

### 1. Parent spec

Run the `to-spec` skill to synthesize the conversation into a spec (no interview) and
publish it as the parent issue.

### 2. Decision register

Collect every decision the plan leaves open, then split by consequence:

- **Broad** (canon-level, cross-cutting, or hard to reverse): ask the owner now, with
  concrete options and a recommendation; wait for ratification before publishing children.
- **Narrow** (bounded to one ticket): embed the exact question in that child's body and
  label the child `may-ask-owner` (create the label if it doesn't exist in the repo), so
  the owner knows to run it interactively, never headless.

Append the ratified decisions to the parent body as a lettered register (`D1`, `D2`, …;
pick the next unused letter series if prior programs already used `D`). Implementation
sessions implement to the register and never re-litigate it.

### 3. Child tickets — the one human gate

Run the `to-tickets` skill against the spec: vertical tracer-bullet children with explicit
blocking edges. Size each child so a fresh implementation session — child body + register +
the code zones and tests it names — stays well under the ~100k-token warning line
(`docs/references/prompting-and-context-guide.md`, CE-2); split a child rather than let it
sprawl, and bundle trivial related items rather than minting micro-issues. The skill's
breakdown quiz is the only human gate: wait for owner approval, then publish the children
under the parent with native blocking relationships and `ready-for-agent`.

### 4. Author the two prompts

Write both prompts against `docs/references/prompting-and-context-guide.md`: standalone
fresh-session briefs (HO-8), tiered context loading (CE-3/CE-4), explicit success criteria
and stopping rules (PR-1), an escape hatch (PR-8). Target ≤800 words each.

**Implementation prompt** — verbatim-runnable, one child per fresh session:

- Names the repo, the parent issue, the program's purpose, and the register as binding —
  no reliance on chat history.
- Task selection: read the parent (spec + register + child list); the task is the
  lowest-numbered OPEN child whose blockers are all CLOSED; if none qualifies, comment
  that on the parent and stop. State the selected child and a one-sentence reason before
  touching anything.
- If the selected child carries `may-ask-owner`, surface its embedded question to the
  owner and wait — never guess an owner decision.
- Context loading, tiered: child body → register → `CLAUDE.md` → `CONTEXT.md` → only the
  code/doc zones the child names plus their seam tests. No whole catalogs, no unrelated
  ADRs.
- Implement with the `implement` skill (TDD at the child's named seams), test external
  behavior only, docs updated in the same change (CLAUDE.md § Keep Documentation Current).
- "Blocked" is a valid outcome: comment the concrete blocker on the child and stop —
  never improvise around a ratified decision.
- Finish: `/code-review` and fix what it finds; full suite green (never skip, xfail, or
  weaken an existing test to pass); commit directly to `main` referencing the child; push
  to `origin main` (the pre-push hook must pass — never bypass it); close the child with a
  summary comment: what shipped, commit hash, suite count, any residue. Then stop —
  exactly one child per session.

**Adversarial review prompt** — run in a fresh session after all children ship:

- Findings, not fixes: edits nothing, closes nothing; deliverable is ONE ranked findings
  report posted as a comment on the parent.
- Verifies the program goal end-to-end, not the diffs alone: re-attack shipped code with
  fresh reproductions; never trust closing comments.
- Checks the decision register was honored exactly, no fix regressed a neighbor, and
  instruction surfaces agree with the mechanisms they describe.
- Runs the project's full test suite itself, plus any repo-specific checks the project's
  agent rules (CLAUDE.md / AGENTS.md) name.
- Ranks findings `fatal | major | minor | polish | watch`, each with a concrete
  reproduction and evidence. "Verified clean" is a valid verdict — do not manufacture
  findings. Ends with an explicit verdict against the program goal.

### 5. Deliver

Post both prompts as one comment on the parent issue, then print them in chat with a link
to the parent. Done when: parent + register + approved children are published and the
prompts are posted and printed.
