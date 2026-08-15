#!/usr/bin/env python3
"""Pre-publish cleanliness check for verified-done.

Scans the publishable file set for:
  - private path or private project-name leaks
  - key-shaped secrets
  - em dashes in Markdown (house style: none)

Exits non-zero if anything is found. Run before any commit intended for a
public push. Dependency-free (stdlib only).

Gitignored, local-only trees (results/live, results/receipts) are skipped, and
this script skips itself since it necessarily contains the patterns it hunts.
"""
import fnmatch
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {".git", "__pycache__"}
SKIP_REL_PREFIXES = ("results/live", "results/receipts")
# Raw ablation rows keep verifier tracebacks, which carry temp directory paths.
# They are local evidence, like results/live. The publishable artifact is the
# ablation.json record next to them, which holds every replicate's outcome.
SKIP_REL_GLOBS = (
    "results/ablation/*/runs/*",
    "results/screens/*/runs/*",
    "results/mutants/*",
)

PRIVATE_PATTERNS = [
    r"/Users/",
    r"/private/var",
    r"~/Desktop",
    r"\bMainFrame\b",
    r"\bagent-harness-eval\b",
    r"\bincome-engine\b",
    r"\bbasic-research-harness\b",
]
# The account name is public and correct inside links to published repos and the
# Pages site. It is a leak anywhere else, most obviously in a filesystem path.
# A check that fires on its own correct output gets ignored, so scope it.
ACCOUNT_ALLOWED = re.compile(
    r"(https?://)?(github\.com/camerontjs-dot|camerontjs-dot\.github\.io)[\w./#?=-]*"
)
ACCOUNT_PATTERN = re.compile(r"\bcamerontjs\b")
SECRET_PATTERNS = [
    r"sk-ant-[A-Za-z0-9_-]{15}",
    r"xox[bp]-",
    r"-----BEGIN [A-Z ]*PRIVATE KEY",
    r"AKIA[0-9A-Z]{16}",
]
EM_DASH = "—"


def _rel(full):
    return os.path.relpath(full, REPO).replace(os.sep, "/")


def iter_files():
    self_rel = _rel(os.path.abspath(__file__))
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            rel = _rel(os.path.join(root, name))
            if rel == self_rel:
                continue
            if rel.startswith(SKIP_REL_PREFIXES):
                continue
            if any(fnmatch.fnmatch(rel, pat) for pat in SKIP_REL_GLOBS):
                continue
            yield rel, os.path.join(root, name)


def main():
    priv = re.compile("|".join(PRIVATE_PATTERNS))
    sec = re.compile("|".join(SECRET_PATTERNS))
    findings = []
    for rel, full in iter_files():
        try:
            with open(full, "r", encoding="utf-8") as f:
                text = f.read()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if priv.search(line):
                findings.append(("private-path", rel, i, line.strip()[:120]))
            if ACCOUNT_PATTERN.search(ACCOUNT_ALLOWED.sub("", line)):
                findings.append(("account-name", rel, i, line.strip()[:120]))
            if sec.search(line):
                findings.append(("secret", rel, i, "<redacted>"))
            if rel.endswith(".md") and EM_DASH in line:
                findings.append(("em-dash", rel, i, line.strip()[:120]))

    if findings:
        print("check_clean: %d issue(s) in the publishable set" % len(findings))
        for kind, rel, i, snippet in findings:
            print("  [%-12s] %s:%d  %s" % (kind, rel, i, snippet))
        return 1
    print("check_clean: clean. No private paths, secrets, or em dashes in the publishable set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
