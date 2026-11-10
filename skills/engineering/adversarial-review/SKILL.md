---
name: adversarial-review
description: Run a shipped program's adversarial review prompt headless on two model families (Claude and GPT) and collect one findings report from each. Use when the user wants a finished program reviewed, asks to run the adversarial review on a parent issue, or when another skill needs the two review reports.
---

# /adversarial-review

Run the adversarial review prompt posted on a program's parent issue twice — once on Claude,
once on GPT — headless, in parallel, each in its own throwaway clone. The deliverable is two
independent findings reports. This skill finds; it does not judge, fix, or file anything.
Turning the reports into work is `/findings-to-program`.

## Instructions

### 1. Name the program

Identify the parent issue. The review prompt is the fenced block under the parent's
"Adversarial review prompt" heading (`/plan-to-program` puts it there). Every child must
be closed; a program reviewed half-shipped produces findings about missing work.

### 2. Run both legs

```bash
python3 <this skill's directory>/scripts/run_review.py --parent <N> --out <scratch dir>
```

Run it from the checkout under review, in the background: a full review takes tens of
minutes per leg. The script refuses, with the reason, when the prompt is missing, a child
is open, or a CLI is absent. Useful flags:

- `--claude-model`, `--gpt-model` — otherwise read from the `claude` and `opencode` rows of
  the project's `config/executors.md` when it has one. Never copy a model id from an old
  record.
- `--post` — also post each report verbatim as a comment on the parent. Use it for a real
  review; leave it off for a trial.
- `--in-place` — review the live checkout instead of clones. Only when the review needs
  files a clone lacks (caches, private data) and no other session is writing there.
- `--legs claude` or `--legs gpt` — one leg, when the other report already exists.
- `--force` — review although children are open; say so when you report.

Both reviewers can run commands — the suite, the CLI, reproductions on throwaway fixtures —
and neither can edit files. A clone keeps their files apart from the owner's work; it is
not a sandbox, so a reviewer may still read outside it (for example, borrow the owner's
virtualenv).

Both legs get the same prompt, verbatim, behind a short preamble that tells the reviewer to
print its report instead of posting it. Neither sees the other's report or this
conversation. Do not add your expectations to the prompt.

### 3. Report

When the script exits, read both reports and tell the owner, per leg: the verdict, the
count of findings by severity, and anything the leg said it had to skip. If a leg failed,
say which and why (its raw log is beside the reports), and ask whether to rerun it or go on
with one — never stand in for a missing leg with a second run of the same family.

Stop there unless the owner asked for more. Do not merge, rank, or dispute the findings
here: that is the synthesis step of `/findings-to-program`, and it reads the two reports
this skill leaves in the output directory (or on the parent, with `--post`).
