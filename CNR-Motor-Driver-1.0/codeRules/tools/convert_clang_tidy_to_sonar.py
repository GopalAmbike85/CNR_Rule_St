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
  Rule      : id, name, description, engineId, cleanCodeAttribute,
              impacts: [{softwareQuality, severity}]
              (softwareQuality in SECURITY/RELIABILITY/MAINTAINABILITY;
               severity in BLOCKER/HIGH/MEDIUM/LOW/INFO;
               cleanCodeAttribute in FORMATTED/CONVENTIONAL/IDENTIFIABLE/
               CLEAR/LOGICAL/COMPLETE/EFFICIENT/FOCUSED/DISTINCT/MODULAR/
               TESTED/LAWFUL/TRUSTWORTHY/RESPECTFUL)
  Issue     : ruleId, primaryLocation, effortMinutes (optional)
  Location  : message, filePath, textRange
  TextRange : startLine, endLine (opt), startColumn (opt), endColumn (opt)

Usage:
  clang-tidy -p <build-dir> file1.c file2.c ... 2>&1 \
    | python3 convert_clang_tidy_to_sonar.py > clang-tidy-sonar.json

Then, in sonar-project.properties or as a -D scanner flag:
  sonar.externalIssuesReportPaths=clang-tidy-sonar.json

v2 (19-08-2026): added the mandatory cleanCodeAttribute field to each Rule.
Confirmed mandatory the hard way: run #30 (0 issues found, so an empty
rules array) passed fine, but run #31 - the first with real findings -
failed with "missing mandatory field 'cleanCodeAttribute'". An earlier
doc fetch had called this field conditionally optional (only required
if severity/type were absent); that turned out to be wrong, or at least
not how SonarQube Cloud's actual validator enforces it - impacts alone
was not sufficient. Trust the real validator error over the docs.
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
# prefixes fall back to MAINTAINABILITY/MEDIUM/CLEAR, a reasonable default
# for a general finding whose exact category isn't otherwise known.
# cleanCodeAttribute picks the closest match from SonarQube's fixed enum
# (FORMATTED/CONVENTIONAL/IDENTIFIABLE/CLEAR/LOGICAL/COMPLETE/EFFICIENT/
# FOCUSED/DISTINCT/MODULAR/TESTED/LAWFUL/TRUSTWORTHY/RESPECTFUL):
#   TRUSTWORTHY - security-related (cert-, security-)
#   LOGICAL     - actual bug/logic-flow findings (bugprone-, clang-analyzer-)
#   EFFICIENT   - performance findings
#   CLEAR       - readability/style findings (readability-, modernize-, misc-)
_CATEGORY_BY_PREFIX = [
    ("cert-",           ("SECURITY", "HIGH", "TRUSTWORTHY")),
    ("security-",       ("SECURITY", "HIGH", "TRUSTWORTHY")),
    ("bugprone-",       ("RELIABILITY", "MEDIUM", "LOGICAL")),
    ("clang-analyzer-", ("RELIABILITY", "MEDIUM", "LOGICAL")),
    ("performance-",    ("RELIABILITY", "LOW", "EFFICIENT")),
    ("readability-",    ("MAINTAINABILITY", "LOW", "CLEAR")),
    ("modernize-",      ("MAINTAINABILITY", "LOW", "CLEAR")),
    ("misc-",           ("MAINTAINABILITY", "LOW", "CLEAR")),
]


def category_for(check_id: str) -> tuple[str, str, str]:
    for prefix, cat in _CATEGORY_BY_PREFIX:
        if check_id.startswith(prefix):
            return cat
    return ("MAINTAINABILITY", "MEDIUM", "CLEAR")


def convert(text: str) -> dict:
    rules: dict[str, dict] = {}
    issues: list[dict] = []

    for raw_line in text.splitlines():
        m = DIAG_RE.match(raw_line.strip())
        if not m:
            continue

        check_id = m.group("check").split(",")[0].strip()

        if check_id not in rules:
            quality, severity, attribute = category_for(check_id)
            rules[check_id] = {
                "id": check_id,
                "name": check_id,
                "description": f"clang-tidy check: {check_id}",
                "engineId": "clang-tidy",
                "cleanCodeAttribute": attribute,
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
