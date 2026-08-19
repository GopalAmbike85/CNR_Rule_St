#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Code Quality Audit — CNR Motor Driver Firmware
#
# Deterministic checker for CodeQualityRules.md / CodeDesignRules.md.
# No LLM call — regex-based Python script (no pip dependencies).
#
# Checks:
#   CQ-1  Function naming in fully-custom files (lower_snake_case)
#   CQ-2  Include guards (#ifndef required, #pragma once prohibited)
#   CD-1  Vendor file immutability (git-diff based, needs --base-ref)
#   CD-2  __weak hook overrides documented with a comment
#   CD-3  CubeMX USER CODE boundary (git-diff based, needs --base-ref)
#   CD-4  motor_telemetry_math.c/h stays MCSDK/HAL-free
#   CD-5  Telemetry math drift review prompt (git-diff based, needs --base-ref)
#
# Outputs:
#   codeRules/reports/CodeQualityErrors.xml
#   codeRules/reports/CodeQualityReport.md
#
# Usage:
#   cd CNR-Motor-Driver-1.0
#   bash codeRules/agents/run-code-quality.sh                     # static rules only
#   bash codeRules/agents/run-code-quality.sh --base-ref origin/main   # + git-diff rules
# ──────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FW_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ ! -d "$FW_ROOT/Src" ]]; then
    echo "ERROR: FW repo not found at $FW_ROOT"
    echo "       Expected CNR-Motor-Driver-1.0/Src/ to exist."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found."
    exit 1
fi

CHECKER="$FW_ROOT/codeRules/tools/code_quality_checker.py"
if [[ ! -f "$CHECKER" ]]; then
    echo "ERROR: Checker not found at $CHECKER"
    exit 1
fi

echo "Code Quality Audit — CNR Motor Driver Firmware"
echo "FW root : $FW_ROOT"
echo ""

python3 "$CHECKER" --fw-root "$FW_ROOT" "$@"

echo ""
echo "Reports:"
echo "  XML : $FW_ROOT/codeRules/reports/CodeQualityErrors.xml"
echo "  MD  : $FW_ROOT/codeRules/reports/CodeQualityReport.md"
