---
name: findings-to-program
description: Turn a finished program's adversarial review into fix work — run the review on two model families, synthesize one findings list, keep only what is worth fixing, and publish that as issues with prompts, following the plan-to-program contract. Use when the user wants review or audit findings turned into issues, a fix program, or a triaged list of what to fix.
---

# /findings-to-program

Turn the adversarial review of a shipped program into fix work: two independent reviews,
one synthesized findings list, a worth-fixing triage, and issues only for what survives it.

Input: the source program's parent issue, which carries the adversarial review prompt, and
any review report already in this conversation or posted on that parent. Mechanics and
prompt contract are those of `/plan-to-program` — read that skill now and follow it; the
deltas below govern where the two differ. This command may launch the review legs in
step 1. It never launches an implementation session, and it ends when the dispositions,
issues and prompts are published.

## Instructions

### 1. Two reviews, independent

A findings list needs one report from each of two model families (Claude and GPT), both
produced from the review prompt on the source parent, verbatim. Use a report that already
exists (in this conversation, or as a comment on the parent). Produce whichever is
missing with the `adversarial-review` skill — read it now and follow it: its script runs
the missing legs headless, in parallel, each in a throwaway clone, with `--post` so each
report lands verbatim on the source parent before you read them side by side.

Neither leg sees the other's report, this conversation, or your expectations. If a leg
cannot run (no quota, no access), say so and ask the owner whether to go on with one —
never fill the gap with a second run of the same family.

### 2. Synthesize

Merge the two reports into one list. One row per distinct defect, however many times and
in however many wordings it was reported; record which leg raised it.

Then check every row against the shipped code yourself. Two legs agreeing is not proof,
and one leg alone is not noise: re-run the reproduction, or read the code the finding
points at. Where the legs disagree on severity, the evidence decides. A row you cannot
reproduce or confirm is marked **not reproduced** with what you tried, and goes no
further.

### 3. Worth fixing?

Give every confirmed row exactly one disposition, with a one-line reason:

- **fix** — a real bug (wrong behavior a real run can reach), a real improvement with a
  named beneficiary, or an extension that clearly serves the program's goal. Gets a child.
- **fold** — true but too small for its own ticket; rides in a child that already touches
  the same code. If no such child exists, it is a watch item.
- **watch** — true, harmless today. Name the event that would make it worth fixing. No
  ticket.
- **reject** — not worth doing. Say why.

Judge against the goal stated on the source parent and the project's own goal hierarchy,
and price each fix (sessions, billed runs, owner attention) against the harm it removes.
Reproduced `fatal` and `major` findings are always **fix**. For everything else the
default is **no ticket**: a finding earns one, it is not owed one. Typical rejects: a
path no real use reaches, polish, a fix that costs more than the defect, a guard for a
guard that no decision reads, a concern that exists only for state the project no longer
has.

Zero fixes is a valid result: post the disposition table on the source parent and stop.

### 4. Decisions

Same split as `/plan-to-program` step 2: broad decisions are asked now and ratified into a
lettered register; narrow ones are embedded in the child body with the `may-ask-owner`
label (create the label if it doesn't exist in the repo). Continue the letter series from
the source program's registers (e.g. after `D` comes `E`) — never reuse a letter.

### 5. The one human gate

Present the full disposition table — every row, with its leg, severity, disposition and
reason, the not-reproduced rows included — and the breakdown of the **fix** rows into
children (titles, blockers, what each covers). The owner may overrule any disposition in
either direction. Publish nothing before approval.

Then publish, sized to what survived:

- **One child's worth of fixes:** a single standalone issue with its own prompt. No
  parent, no register unless a decision needs one.
- **More:** a new parent that references the source parent and both reports; children
  with native blocking relationships and `ready-for-agent`. Bundle small related fixes
  into one child; split any child whose fix would push a fresh session past the
  ~100k-token warning line.

Either way the disposition table is published (in the new parent body, or as a comment on
the source parent), so the next review can verify each **fix** and knows what was already
ruled on.

### 6. The two prompts

Read the implementation/review prompt pair on the source parent and carry over its proven
structure, updated to this program's scope. Both follow the contract in `/plan-to-program`
step 4, with these additions to the review prompt:

- It verifies the **cumulative surface** — the original program's goal end-to-end with all
  fixes applied, not the fix-diffs alone.
- For each **fix** row it attempts a fresh reproduction against shipped code to confirm
  the finding is closed.
- It lists the **watch** and **reject** rows as already ruled on: a reviewer re-raises one
  only with new evidence, and says what is new.

A single standalone issue gets one implementation prompt and no review prompt, unless the
fix is critical enough that the owner asks for one.

### 7. Deliver

Per `/plan-to-program` step 5: the prompts as one comment on the new parent (or on the
standalone issue), printed in chat with a link, beside the final disposition table.
