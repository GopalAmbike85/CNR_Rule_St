#!/usr/bin/env python3
"""
Converts clang-tidy's plain-text diagnostic output into SonarQube's Generic
Issue Import Format, so clang-tidy findings (const-correctness, narrowing
conversions, unused return values, etc. - the checks code_quality_checker.py
deliberately does NOT attempt via regex) show up in the Sonar dashboard
alongside the official cfamily analyzer's own issues.

Schema cross-checked against two independently-fetched sources on
18-08-2026 (SonarQube Cloud's "generic-issue-data" doc and SonarQube Server
10.8's "generic-issue-import-format" doc) - both agree on the field names
used here, which is why this is trusted despite one earlier fetch attempt
of the same docs returning a 404 shell instead of content.

  Top level : {"rules": [...], "issues": [...]}
  Rule      : id, name, description, engineId,
              impacts: [{softwareQuality, severity}]
              (softwareQuality in SECURITY/RELIABILITY/MAINTAINABILITY;
               severity in BLOCKER/HIGH/MEDIUM/LOW/INFO)
  Issue     : ruleId, primaryLocation, effortMinutes (optional)
  Location  : message, filePath, textRange
  TextRange : startLine, endLine (opt), startColumn (opt), endColumn (opt)

Usage:
  clang-tidy -p <build-dir> file1.c file2.c ... 2>&1 \
    | python3 convert_clang_tidy_to_sonar.py > clang-tidy-sonar.json

Then, in sonar-project.properties or as a -D scanner flag:
  sonar.externalIssuesReportPaths=clang-tidy-sonar.json

NOT YET RUN AGAINST REAL clang-tidy OUTPUT FROM THE ACTUAL FIRMWARE - no
access to that repo. Self-tested against a synthetic sample mimicking
clang-tidy's real diagnostic line format instead (see test invocation in
codeRules/session_history, or re-run: this script accepts any clang-tidy
-style stdin, so feeding it a real clang-tidy run's output is the only
remaining validation step once the real repo is available).
"""
import json
import re
import sys

# clang-tidy's default diagnostic line shape:
#   /path/to/file.c:12:5: warning: message text [check-name]
# A line can also end with a second, comma-separated check name, e.g.
# "[bugprone-foo,-warnings-as-errors]" - split(",")[0] below takes the
# first as the primary rule id.
DIAG_RE = re.compile(
    r'^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): '
    r'(?P<level>warning|error): (?P<message>.+?) \[(?P<check>[\w,.\-]+)\]$'
)

# Best-effort category mapping by clang-tidy check-name prefix. This is a
# judgment call, not something SonarQube or clang-tidy defines - unmapped
# prefixes fall back to MAINTAINABILITY/MEDIUM, a reasonable default for a
# general finding whose exact category isn't otherwise known.
_CATEGORY_BY_PREFIX = [
    ("cert-",           ("SECURITY", "HIGH")),
    ("security-",       ("SECURITY", "HIGH")),
    ("bugprone-",       ("RELIABILITY", "MEDIUM")),
    ("clang-analyzer-", ("RELIABILITY", "MEDIUM")),
    ("performance-",    ("RELIABILITY", "LOW")),
    ("readability-",    ("MAINTAINABILITY", "LOW")),
    ("modernize-",      ("MAINTAINABILITY", "LOW")),
    ("misc-",           ("MAINTAINABILITY", "LOW")),
]


def category_for(check_id: str) -> tuple[str, str]:
    for prefix, cat in _CATEGORY_BY_PREFIX:
        if check_id.startswith(prefix):
            return cat
    return ("MAINTAINABILITY", "MEDIUM")


def convert(text: str) -> dict:
    rules: dict[str, dict] = {}
    issues: list[dict] = []

    for raw_line in text.splitlines():
        m = DIAG_RE.match(raw_line.strip())
        if not m:
            continue

        check_id = m.group("check").split(",")[0].strip()

        if check_id not in rules:
            quality, severity = category_for(check_id)
            rules[check_id] = {
                "id": check_id,
                "name": check_id,
                "description": f"clang-tidy check: {check_id}",
                "engineId": "clang-tidy",
                "impacts": [{"softwareQuality": quality, "severity": severity}],
            }

        issues.append({
            "ruleId": check_id,
            "primaryLocation": {
                "message": m.group("message"),
                "filePath": m.group("file"),
                "textRange": {
                    "startLine": int(m.group("line")),
                    "startColumn": int(m.group("col")),
                },
            },
        })

    return {"rules": list(rules.values()), "issues": issues}


def main() -> int:
    result = convert(sys.stdin.read())
    json.dump(result, sys.stdout, indent=2)
    print()
    print(f"Converted {len(result['issues'])} issue(s), "
          f"{len(result['rules'])} distinct rule(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
