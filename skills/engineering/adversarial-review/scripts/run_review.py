#!/usr/bin/env python3
"""Run a program's adversarial review prompt on two model families, headless and in parallel.

Reads the review prompt from the program's parent issue, runs it once through `claude -p` and once
through `opencode run`, each in its own throwaway clone, and writes one findings report per leg.
Both legs run without file-edit tools: a reviewer reads and runs commands, it does not edit.
Standard library only. Exit codes: 0 every requested leg reported; 1 a leg failed (the other
report is kept); 2 refused before running (the reason is on stderr).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HEADING = re.compile(r"^#{1,6}\s.*adversarial review prompt.*$", re.IGNORECASE | re.MULTILINE)
FENCE = re.compile(r"^(`{3,})[^\n]*\n(.*?)^\1\s*$", re.DOTALL | re.MULTILINE)
OPENCODE_MODEL = re.compile(r"\|\s*opencode\s*\|[^|]*?-m\s+(\S+)")
CLAUDE_MODEL = re.compile(r"\|\s*claude\s*\|[^|]*?--model\s+(\S+)")

PREAMBLE = """\
You are one of two independent reviewers running this review headless. Three rules override
anything below that conflicts with them:
- Do not post, comment, push, commit or close anything. Your deliverable is the complete
  findings report, printed as your final message and nowhere else. The caller posts it.
- You are working in {where} at {sha}. {absent}
- If a step names a tool you do not have, skip it and say so in the report.

The review prompt follows.

"""
CLONE_NOTE = (
    "Files that are untracked or git-ignored in the owner's checkout (caches, private data, "
    "virtualenvs) are absent here. If a step needs one, skip that step and say so in the report."
)
IN_PLACE_NOTE = "Other sessions may be working in it: change no tracked file and never `git stash`."


def refuse(message: str):
    print(f"refused: {message}", file=sys.stderr)
    sys.exit(2)


def run(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(argv, text=True, capture_output=True, check=False, **kwargs)


def gh_json(args: list[str]):
    proc = run(["gh", *args])
    if proc.returncode != 0:
        refuse(f"`gh {' '.join(args)}` failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def extract_review_prompt(comments: list[dict], body: str) -> str:
    """The first fenced block under the last "adversarial review prompt" heading on the parent."""
    for text in [*(c["body"] for c in reversed(comments)), body]:
        headings = list(HEADING.finditer(text))
        if not headings:
            continue
        fence = FENCE.search(text, headings[-1].end())
        if fence and fence.group(2).strip():
            return fence.group(2).strip() + "\n"
    refuse(
        "no fenced block under an 'Adversarial review prompt' heading on the parent issue or its "
        "comments; pass --prompt-file"
    )


def open_children(repo: str, parent: int) -> list[int] | None:
    proc = run(["gh", "api", f"repos/{repo}/issues/{parent}/sub_issues", "--paginate"])
    if proc.returncode != 0:
        return None
    return [c["number"] for c in json.loads(proc.stdout or "[]") if c.get("state") == "open"]


def model_from_executors(checkout: Path, pattern: re.Pattern) -> str | None:
    table = checkout / "config" / "executors.md"
    if not table.is_file():
        return None
    match = pattern.search(table.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def opencode_text(stdout: str) -> str:
    """The last assistant message from `opencode run --format json`'s event stream."""
    messages: dict[str, list[str]] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "text":
            continue
        part = event.get("part", {})
        if isinstance(part.get("text"), str):
            messages.setdefault(part.get("messageID", ""), []).append(part["text"])
    return "\n".join(list(messages.values())[-1]) if messages else ""


def claude_text(stdout: str) -> str:
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return ""
    if result.get("is_error"):
        return ""
    return result.get("result") or ""


GPT_AGENT = "adversarial-reviewer"
# The GPT leg's agent, injected for this one invocation through OPENCODE_CONFIG_CONTENT: file edits
# denied, like opencode's built-in `plan` agent, but without plan mode's instruction to run nothing
# that writes. Under `plan` the reviewer declined to build fixtures or run the suite and returned
# a static read (measured on the first trial).
GPT_AGENT_CONFIG = {
    "agent": {
        GPT_AGENT: {
            "mode": "primary",
            "description": "Read-and-run adversarial reviewer: no file edits.",
            "prompt": (
                "You are an adversarial reviewer. You cannot edit files and must not try to. "
                "You are expected to run commands: the test suite, the project's CLI, and "
                "reproductions on throwaway fixtures created under the system temp directory."
            ),
            "permission": {"edit": "deny", "bash": "allow", "webfetch": "deny"},
        }
    }
}


def leg_argv(leg: str, model: str | None, workdir: Path) -> list[str]:
    if leg == "gpt":
        argv = ["opencode", "run", "--agent", GPT_AGENT, "--format", "json", "--dir", str(workdir)]
        return argv + (["-m", model] if model else [])
    argv = ["claude", "-p", "--output-format", "json"]
    if model:
        argv += ["--model", model]
    return argv + [
        "--allowedTools", "Bash", "Read", "Grep", "Glob",
        "--disallowedTools", "Edit", "Write", "NotebookEdit",
    ]


def run_leg(leg: str, model: str | None, prompt: str, workdir: Path, out: Path,
            parent: int, timeout: int) -> tuple[str, bool, str]:
    argv = leg_argv(leg, model, workdir)
    started = time.time()
    try:
        if leg == "gpt":
            env = {**os.environ, "OPENCODE_CONFIG_CONTENT": json.dumps(GPT_AGENT_CONFIG)}
            proc = run([*argv, prompt], cwd=workdir, timeout=timeout, env=env)
        else:
            proc = run(argv, input=prompt, cwd=workdir, timeout=timeout)
    except subprocess.TimeoutExpired:
        return leg, False, f"timed out after {timeout}s"
    (out / f"review-{parent}-{leg}.raw.log").write_text(
        proc.stdout + "\n--- stderr ---\n" + proc.stderr, encoding="utf-8"
    )
    text = (opencode_text if leg == "gpt" else claude_text)(proc.stdout).strip()
    minutes = (time.time() - started) / 60
    if proc.returncode != 0 or not text:
        return leg, False, f"exit {proc.returncode}, no report text ({minutes:.0f} min); see the raw log"
    (out / f"review-{parent}-{leg}.md").write_text(text + "\n", encoding="utf-8")
    return leg, True, f"{len(text.split())} words, {minutes:.0f} min"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--parent", type=int, required=True, help="the program's parent issue")
    parser.add_argument("--repo", help="owner/name (default: the checkout's GitHub repo)")
    parser.add_argument("--dir", default=".", help="the checkout to review (default: cwd)")
    parser.add_argument("--out", required=True, help="directory for reports, logs and clones")
    parser.add_argument("--legs", default="claude,gpt", help="comma list of claude,gpt")
    parser.add_argument("--claude-model", help="default: the claude row of config/executors.md, else the CLI's")
    parser.add_argument("--gpt-model", help="default: the opencode row of config/executors.md")
    parser.add_argument("--prompt-file", help="use this prompt instead of the parent's")
    parser.add_argument("--in-place", action="store_true",
                        help="run in the checkout itself instead of a throwaway clone per leg")
    parser.add_argument("--force", action="store_true", help="run although children are open")
    parser.add_argument("--post", action="store_true",
                        help="post each report verbatim as a comment on the parent")
    parser.add_argument("--timeout", type=int, default=5400, help="seconds per leg (default 5400)")
    args = parser.parse_args()

    checkout = Path(args.dir).resolve()
    legs = [leg.strip() for leg in args.legs.split(",") if leg.strip()]
    if not legs or set(legs) - {"claude", "gpt"}:
        refuse(f"--legs takes claude and/or gpt, got {args.legs!r}")
    for leg, binary in (("claude", "claude"), ("gpt", "opencode")):
        if leg in legs and not shutil.which(binary):
            refuse(f"`{binary}` is not on PATH (needed for the {leg} leg)")
    sha_proc = run(["git", "rev-parse", "HEAD"], cwd=checkout)
    if sha_proc.returncode != 0:
        refuse(f"{checkout} is not a git checkout")
    sha = sha_proc.stdout.strip()

    repo = args.repo or gh_json(["repo", "view", "--json", "nameWithOwner"])["nameWithOwner"]
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        issue = gh_json(["issue", "view", str(args.parent), "--repo", repo, "--json", "body,comments"])
        prompt = extract_review_prompt(issue["comments"], issue["body"])

    still_open = open_children(repo, args.parent)
    if still_open and not args.force:
        refuse(f"children still open: {', '.join(f'#{n}' for n in still_open)} (pass --force to review anyway)")
    if still_open is None:
        print("note: could not list sub-issues; not checking that the children are closed", file=sys.stderr)

    models = {
        "claude": args.claude_model or model_from_executors(checkout, CLAUDE_MODEL),
        "gpt": args.gpt_model or model_from_executors(checkout, OPENCODE_MODEL),
    }
    if "gpt" in legs and not models["gpt"]:
        refuse("no GPT model: pass --gpt-model (a headless opencode run does not inherit one)")

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    full_prompt = PREAMBLE.format(
        sha=sha[:12],
        where="the owner's live checkout" if args.in_place else "a throwaway clone of the repository",
        absent=IN_PLACE_NOTE if args.in_place else CLONE_NOTE,
    ) + prompt
    (out / f"review-{args.parent}-prompt.md").write_text(full_prompt, encoding="utf-8")

    workdirs = {}
    for leg in legs:
        if args.in_place:
            workdirs[leg] = checkout
            continue
        clone = out / f"clone-{leg}"
        if clone.exists():
            shutil.rmtree(clone)
        proc = run(["git", "clone", "--quiet", str(checkout), str(clone)])
        if proc.returncode != 0:
            refuse(f"could not clone {checkout}: {proc.stderr.strip()}")
        workdirs[leg] = clone

    print(f"reviewing {repo}#{args.parent} at {sha[:12]}: " +
          ", ".join(f"{leg} ({models[leg] or 'CLI default'})" for leg in legs), file=sys.stderr)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(legs)) as pool:
        results = list(pool.map(
            lambda leg: run_leg(leg, models[leg], full_prompt, workdirs[leg], out, args.parent,
                                args.timeout),
            legs,
        ))

    failed = False
    for leg, ok, detail in results:
        report = out / f"review-{args.parent}-{leg}.md"
        print(f"{leg}: {'report at ' + str(report) if ok else 'FAILED'} ({detail})")
        failed |= not ok
        if ok and args.post:
            header = (f"## Adversarial review: {leg} leg ({models[leg] or 'CLI default'}), "
                      f"at `{sha[:12]}`\n\nPosted verbatim by `run_review.py`; "
                      "not yet synthesized or triaged.\n\n")
            posted = run(["gh", "issue", "comment", str(args.parent), "--repo", repo,
                          "--body", header + report.read_text(encoding="utf-8")])
            print(f"{leg}: {'posted ' + posted.stdout.strip() if posted.returncode == 0 else 'POST FAILED ' + posted.stderr.strip()}")
            failed |= posted.returncode != 0
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
