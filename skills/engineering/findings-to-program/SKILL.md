---
name: findings-to-program
description: Turn a review's findings into an issue-tracker fix program — a parent that closes every finding, blocked children, and implementation and review prompts, following the plan-to-program contract.
disable-model-invocation: true
---

# /findings-to-program

Turn the review findings in this conversation into a GitHub fix program — a new parent
issue and children that, once all shipped, close every finding — plus implementation and
review prompts posted on the new parent.

Input: the current conversation (an adversarial review that produced findings) and the
source program's parent issue, if one exists. Mechanics and prompt contract are those of
`/plan-to-program` — read `.opencode/commands/plan-to-program.md` now and follow it; the
deltas below govern where the two differ. This command ends when the issues and prompts
are published — never launch an implementation or review session yourself.

## Instructions

### 1. Total coverage

Build an explicit finding → child map covering **every** finding, including minor, polish,
and watch items. Bundle small related findings into one child; split any child whose fix
would push a fresh session past the ~100k-token warning line. Publish the map in the new
parent body so the review prompt can later verify closure finding by finding.

### 2. Decisions

Same split as `/plan-to-program` step 2: broad decisions are asked now and ratified into a
lettered register on the parent; narrow ones are embedded in the child body with the
`may-ask-owner` label (create the label if it doesn't exist in the repo). Continue the
letter series from the source program's registers (e.g. after `D` comes `E`) — never reuse
a letter.

### 3. The one human gate

Present the finding → child map and the breakdown (titles, blockers, what each bundle
covers) for owner approval before publishing anything. Then publish: the new parent
references the source program's parent and the findings report; children carry native
blocking relationships and `ready-for-agent`.

### 4. The two prompts

Read the implementation/review prompt pair on the source program's parent and carry over
its proven structure, updated to this program's scope. Both prompts follow the contract in
`/plan-to-program` step 4, with one addition: the review prompt verifies the **cumulative
surface** — the original program's goal end-to-end with all fixes applied, not the
fix-diffs alone — and, for each entry in the finding → child map, attempts a fresh
reproduction against shipped code to confirm the finding is actually closed.

### 5. Deliver

Per `/plan-to-program` step 5: both prompts as one comment on the new parent, printed in
chat with a link.
