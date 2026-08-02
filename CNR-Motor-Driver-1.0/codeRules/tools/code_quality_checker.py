#!/usr/bin/env python3
"""Deterministic checker for CodeQualityRules.md / CodeDesignRules.md.

No LLM call - plain regex/AST-free text checks, matching the rules docs in
codeRules/. Run from the project root (CNR-Motor-Driver-1.0/).

Usage:
    python3 codeRules/tools/code_quality_checker.py [--base-ref origin/main]

--base-ref enables the git-diff-based rules (vendor file modified, CubeMX
USER CODE boundary, telemetry math drift prompt). Without it, only the
static rules run (function naming, include guards, forbidden includes).
"""

import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

VENDOR_MARKER = "Motor Control SDK Team"
USER_CODE_BEGIN = re.compile(r"USER CODE BEGIN")
USER_CODE_END = re.compile(r"USER CODE END")

# Files known to be fully custom (Rule scope table in CodeQualityRules.md).
# Recomputed by find_custom_files() below - this constant is only a fallback
# label, not the source of truth.
TELEMETRY_MATH_FILES = ("Src/motor_telemetry_math.c", "Inc/motor_telemetry_math.h")
ALLOWED_TELEMETRY_INCLUDES = {"stdint.h", "stdbool.h", "math.h"}

# CubeMX runtime glue: not vendor-authored (no ST-team header) but not
# project-custom either - pure toolchain boilerplate, essentially never
# hand-edited. Excluded from style rules entirely (see CodeQualityRules.md
# Scope table, "CubeMX runtime glue" row).
CUBEMX_RUNTIME_GLUE = {"Src/syscalls.c", "Src/sysmem.c", "Src/system_stm32g4xx.c"}


def find_source_files(root):
    files = sorted(root.glob("Src/*.c")) + sorted(root.glob("Inc/*.h"))
    return files


def is_vendor_file(path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return VENDOR_MARKER in text


def has_user_code_markers(path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(USER_CODE_BEGIN.search(text))


def find_custom_files(root):
    """Fully-custom files only: no ST MCSDK header, no CubeMX USER CODE
    markers, not CubeMX runtime glue. This is the actual scope for CQ-1/CQ-2
    style rules - see CodeQualityRules.md Scope table. Everything else is
    either vendor code (Rule 0) or CubeMX-generated code whose style is not
    ours to enforce (only its USER CODE *contents* are checked, by CD-3's
    git-diff-based rule, not by these static style rules)."""
    result = []
    for f in find_source_files(root):
        rel = str(f.relative_to(root)).replace("\\", "/")
        if is_vendor_file(f) or has_user_code_markers(f) or rel in CUBEMX_RUNTIME_GLUE:
            continue
        result.append(f)
    return result


def find_user_code_files(root):
    """Files containing CubeMX USER CODE markers (vendor or not) - used only
    by the CD-3 git-diff boundary check, not by static style rules."""
    return [f for f in find_source_files(root) if has_user_code_markers(f)]


class Finding:
    def __init__(self, rule, severity, file, line, category, message, recommendation):
        self.rule = rule
        self.severity = severity
        self.file = file
        self.line = line
        self.category = category
        self.message = message
        self.recommendation = recommendation


# ─── CQ-1: function naming in fully-custom files ───────────────────────────
FUNC_DEF_RE = re.compile(
    r"^(?:static\s+)?[A-Za-z_][A-Za-z0-9_]*\s*\*?\s*\b([A-Za-z_][A-Za-z0-9_]*)\s*\("
)
SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def check_function_naming(root, custom_files, weak_names):
    findings = []
    for f in custom_files:
        if f.suffix != ".c":
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, start=1):
            m = FUNC_DEF_RE.match(line.strip())
            if not m:
                continue
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "return", "sizeof"):
                continue
            if name in weak_names:
                continue  # Rule 1.2 exception - overriding a vendor __weak hook
            if not SNAKE_CASE_RE.match(name):
                findings.append(Finding(
                    "CQ-1", "Error", str(f.relative_to(root)), i, "FunctionNaming",
                    f"Function '{name}' does not follow lower_snake_case",
                    f"Rename to a lower_snake_case equivalent, or confirm it overrides "
                    f"a vendor __weak hook (Rule 1.2) if not renameable.",
                ))
    return findings


# ─── CQ-2: include guards / no #pragma once ────────────────────────────────
def check_include_guards(root, custom_files):
    findings = []
    for f in custom_files:
        if f.suffix != ".h":
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        expected = f.stem.upper().replace("-", "_") + "_H"
        if any("pragma once" in l for l in lines[:30]):
            findings.append(Finding(
                "CQ-2", "Blocking", str(f.relative_to(root)), 1, "IncludeGuard",
                "#pragma once used instead of #ifndef guard",
                f"Replace with #ifndef {expected} / #define {expected}",
            ))
            continue
        # File-header doxygen comment blocks can run 15-20+ lines before the
        # guard - search the whole file for the FIRST #ifndef, not just a
        # fixed prefix window.
        guard_lines = [l for l in lines if l.strip().startswith("#ifndef")]
        if not guard_lines:
            findings.append(Finding(
                "CQ-2", "Error", str(f.relative_to(root)), 1, "IncludeGuard",
                "No #ifndef include guard found in first 15 lines",
                f"Add #ifndef {expected} / #define {expected}",
            ))
        elif expected not in guard_lines[0]:
            findings.append(Finding(
                "CQ-2", "Error", str(f.relative_to(root)),
                lines.index(guard_lines[0]) + 1, "IncludeGuard",
                f"Include guard does not match filename (expected {expected})",
                f"Rename guard to {expected}",
            ))
    return findings


# ─── CD-4: motor_telemetry_math.c/h must stay MCSDK/HAL-free ───────────────
INCLUDE_RE = re.compile(r'^\s*#include\s*[<"]([^">]+)[>"]')


def check_telemetry_includes(root):
    findings = []
    for rel in TELEMETRY_MATH_FILES:
        f = root / rel
        if not f.exists():
            continue
        own_header = f.stem + ".h"  # a .c may always include its own paired .h
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            m = INCLUDE_RE.match(line)
            if not m:
                continue
            header = m.group(1)
            base = header.split("/")[-1]
            if base in ALLOWED_TELEMETRY_INCLUDES or base == own_header:
                continue
            findings.append(Finding(
                "CD-4", "Blocking", rel, i, "HostTestabilityBoundary",
                f"Unexpected include '{header}' in a host-testable module",
                "Remove, or confirm it is not an MCSDK/HAL header before allowing it",
            ))
    return findings


# ─── CD-2: __weak overrides must carry an explanatory comment ──────────────
WEAK_RE = re.compile(r"__weak\s+[A-Za-z_][A-Za-z0-9_ *]*\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def find_weak_names(root):
    """Every vendor-declared __weak function name, for the Rule 1.2 exception list."""
    names = set()
    for f in find_source_files(root):
        if not is_vendor_file(f):
            continue
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = WEAK_RE.search(line)
            if m:
                names.add(m.group(1))
    return names


def check_weak_overrides_documented(root, custom_files, weak_names):
    findings = []
    for f in custom_files:
        if f.suffix != ".c":
            continue
        lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, start=1):
            m = FUNC_DEF_RE.match(line.strip())
            if not m or m.group(1) not in weak_names:
                continue
            window = "\n".join(lines[max(0, i - 11):i])
            if "/*" not in window and "//" not in window:
                findings.append(Finding(
                    "CD-2", "Error", str(f.relative_to(root)), i, "WeakHookOverride",
                    f"Override of vendor __weak function '{m.group(1)}' has no nearby "
                    f"explanatory comment",
                    "Add a comment stating why this deviates from MCSDK default behavior",
                ))
    return findings


# ─── Git-diff-based rules: CD-1 (vendor immutability), CD-3 (USER CODE) ────
def git_changed_files(root, base_ref):
    # --relative makes paths relative to `cwd` (FW_ROOT) rather than the
    # repo top level. FW_ROOT can be a subdirectory of the actual git repo
    # (e.g. this project lives under a parent "Testing" repo) - without
    # --relative every path lookup below silently fails to match.
    try:
        out = subprocess.run(
            ["git", "diff", "--relative", "--name-only", f"{base_ref}...HEAD", "--", "Src", "Inc"],
            cwd=root, capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"WARNING: git diff failed ({e}); skipping diff-based rules", file=sys.stderr)
        return []
    return [root / p for p in out.stdout.splitlines() if p]


def git_changed_line_numbers(root, base_ref, path):
    """Line numbers changed in `path` relative to base_ref, via unified diff hunks."""
    try:
        out = subprocess.run(
            ["git", "diff", "--relative", "-U0", f"{base_ref}...HEAD", "--",
             str(path.relative_to(root))],
            cwd=root, capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    lines = set()
    for hunk in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", out.stdout, re.MULTILINE):
        start = int(hunk.group(1))
        count = int(hunk.group(2)) if hunk.group(2) else 1
        lines.update(range(start, start + max(count, 1)))
    return lines


def check_vendor_immutability(root, base_ref):
    findings = []
    for f in git_changed_files(root, base_ref):
        if not f.exists() or not is_vendor_file(f):
            continue
        user_code_lines = user_code_marker_ranges(f)
        changed = git_changed_line_numbers(root, base_ref, f)
        outside = changed - user_code_lines
        if outside:
            findings.append(Finding(
                "CD-1", "Blocking", str(f.relative_to(root)), min(outside), "VendorFileModified",
                f"Vendor file modified outside USER CODE markers "
                f"({len(outside)} line(s): {sorted(outside)[:5]}{'...' if len(outside) > 5 else ''})",
                "Revert; override via a __weak hook instead (see CodeDesignRules.md Rule 2)",
            ))
    return findings


def user_code_marker_ranges(path):
    """Set of line numbers considered 'inside' a USER CODE BEGIN/END block."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    in_block = False
    allowed = set()
    for i, line in enumerate(lines, start=1):
        if USER_CODE_BEGIN.search(line):
            in_block = True
        if in_block:
            allowed.add(i)
        if USER_CODE_END.search(line):
            in_block = False
    return allowed


def check_cubemx_boundary(root, base_ref):
    findings = []
    user_code_files = {f for f in find_user_code_files(root)}
    for f in git_changed_files(root, base_ref):
        if f not in user_code_files or not f.exists():
            continue
        allowed = user_code_marker_ranges(f)
        changed = git_changed_line_numbers(root, base_ref, f)
        outside = changed - allowed
        if outside:
            findings.append(Finding(
                "CD-3", "Blocking", str(f.relative_to(root)), min(outside), "CubeMXUserCodeBoundary",
                f"Change outside USER CODE markers ({len(outside)} line(s): "
                f"{sorted(outside)[:5]}{'...' if len(outside) > 5 else ''})",
                "Move the change inside a USER CODE BEGIN/END block, or it will be "
                "lost on the next CubeMX regeneration",
            ))
    return findings


def check_telemetry_drift_prompt(root, base_ref):
    changed = {str(f.relative_to(root)) for f in git_changed_files(root, base_ref) if f.exists()}
    touched = changed & {"Src/main.c", "Src/motor_telemetry_math.c", "Inc/motor_telemetry_math.h"}
    if not touched:
        return []
    return [Finding(
        "CD-5", "ReviewPrompt", ", ".join(sorted(touched)), 0, "TelemetryMathDrift",
        "This PR touches telemetry/diagnostic math shared between main.c and "
        "motor_telemetry_math.c",
        "Confirm the other file's formulas still match, or explain why they now "
        "intentionally diverge (see CodeDesignRules.md Rule 5)",
    )]


# ─── Reporting ──────────────────────────────────────────────────────────────
def write_xml(findings, out_path):
    errors = [f for f in findings if f.severity != "ReviewPrompt"]
    root_el = ET.Element("codeQualityReport", generated="YYYY-MM-DD", totalErrors=str(len(errors)))
    for i, f in enumerate(findings, start=1):
        ET.SubElement(root_el, "error", id=str(i), rule=f.rule, severity=f.severity,
                       file=f.file, line=str(f.line), category=f.category,
                       message=f.message, recommendation=f.recommendation)
    tree = ET.ElementTree(root_el)
    ET.indent(tree, space="  ")
    tree.write(out_path, encoding="UTF-8", xml_declaration=True)


def write_markdown(findings, out_path):
    errors = [f for f in findings if f.severity != "ReviewPrompt"]
    prompts = [f for f in findings if f.severity == "ReviewPrompt"]
    lines = [
        "# Code Quality Report", "",
        f"**Total Errors:** {len(errors)}",
        f"**Review Prompts (not auto-verified):** {len(prompts)}", "",
        "## Errors", "",
        "| Rule | Severity | File | Line | Message | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for f in errors:
        lines.append(f"| {f.rule} | {f.severity} | {f.file} | {f.line} | {f.message} | {f.recommendation} |")
    lines += ["", "## Review Prompts", "",
              "| Rule | File | Message | Recommendation |", "|---|---|---|---|"]
    for f in prompts:
        lines.append(f"| {f.rule} | {f.file} | {f.message} | {f.recommendation} |")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fw-root", default=".", help="Path to CNR-Motor-Driver-1.0/")
    parser.add_argument("--base-ref", default=None,
                         help="Git ref to diff against for CD-1/CD-3/CD-5 (e.g. origin/main)")
    args = parser.parse_args()

    root = Path(args.fw_root).resolve()
    if not (root / "Src").is_dir():
        print(f"ERROR: {root}/Src not found", file=sys.stderr)
        sys.exit(1)

    custom_files = find_custom_files(root)
    weak_names = find_weak_names(root)

    findings = []
    findings += check_function_naming(root, custom_files, weak_names)
    findings += check_include_guards(root, custom_files)
    findings += check_telemetry_includes(root)
    findings += check_weak_overrides_documented(root, custom_files, weak_names)

    if args.base_ref:
        findings += check_vendor_immutability(root, args.base_ref)
        findings += check_cubemx_boundary(root, args.base_ref)
        findings += check_telemetry_drift_prompt(root, args.base_ref)
    else:
        print("NOTE: --base-ref not given, skipping CD-1/CD-3/CD-5 (git-diff-based rules)",
              file=sys.stderr)

    reports_dir = root / "codeRules" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_xml(findings, reports_dir / "CodeQualityErrors.xml")
    write_markdown(findings, reports_dir / "CodeQualityReport.md")

    errors = [f for f in findings if f.severity != "ReviewPrompt"]
    print(f"Custom/in-scope files checked: {len(custom_files)}")
    print(f"Errors: {len(errors)}  Review prompts: {len(findings) - len(errors)}")
    print(f"Reports written to {reports_dir}")

    blocking = [f for f in errors if f.severity == "Blocking"]
    if blocking:
        print(f"BLOCKING findings: {len(blocking)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
