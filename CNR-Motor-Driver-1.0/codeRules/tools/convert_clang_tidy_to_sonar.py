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

v3 (19-08-2026): dropped startColumn from textRange (now startLine only
- a whole-line range). Confirmed via run #34's real scanner crash:
  java.lang.IllegalArgumentException: Start pointer [line=319,
  lineOffset=9] should be before end pointer [line=319, lineOffset=9]
Traced to Src/aspep.c line 319, which is a lone "        {" - 9
characters, column 9 is the LAST character on the line. SonarQube's
external-issue importer widens a column-only point into a valid range
by advancing the end column by one; here that would run past
end-of-line, so it clamps back to the same column as the start,
producing an exact start==end pointer, which its own range validator
then rejects. This never surfaced with clang-tidy scoped to just
motor_telemetry_math.c; across the ~50 files now in scope (see the
workflow's v15 change), a short line ending in a single brace is
common and effectively guaranteed to recur. Whole-line ranges (no
column) sidestep this entire class of edge case rather than trying to
special-case "column at end of line" - the Generic Issue Import format
supports startLine alone (endLine/columns are all optional).
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
                # startColumn deliberately omitted - see v3 changelog note
                # above (a column pointing at the last character of a
                # short line crashes SonarQube's range widening). Whole
                # line is precise enough to locate the finding.
                "textRange": {
                    "startLine": int(m.group("line")),
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
