# Code Quality Rules (CNR Motor Driver Firmware)

Version: v1
Date: 02-08-2026

## Purpose

Verify naming, header, and style conventions for the code this project actually
owns, without imposing an invented convention on ST's Motor Control SDK (MCSDK)
code that ships with the project.

> **Related:** Architecture/layering rules are in [CodeDesignRules.md](CodeDesignRules.md).
> **Ground truth:** conventions below were read from the actual source in
> `Src/`/`Inc/`, not invented. See "How this was verified" under each rule.

---

## Scope

This codebase is almost entirely ST-authored or tool-generated. Verified by
grepping every file under `Src/`/`Inc/` for the string `Motor Control SDK Team`
(ST's own file-header author tag) on 02-08-2026:

| Category | Count | Examples | In scope for these rules? |
|---|---|---|---|
| ST MCSDK vendor code (`Motor Control SDK Team` header) | 47 of 58 | `mc_tasks.c`, `pwm_curr_fdbk.c`, `aspep.c`, `mcp.c`, `motorcontrol.c` | **No** — see Rule 0 |
| STM32CubeMX-generated, has `USER CODE BEGIN/END` markers, no ST-team header | `main.c`, `main.h`, `stm32g4xx_it.c/.h`, `stm32g4xx_hal_msp.c` | **Only the `USER CODE` blocks** |
| CubeMX runtime glue, essentially never hand-edited | `syscalls.c`, `sysmem.c`, `system_stm32g4xx.c` | **No** (flag any edit for manual review, don't auto-check style) |
| Fully custom, no vendor/tool provenance | `motor_telemetry_math.c`, `motor_telemetry_math.h` | **Yes — full scope** |

Re-run the grep below whenever new files are added; do not hardcode this list
as permanent — a future PR may add more custom modules.

```bash
for f in Src/*.c Inc/*.h; do
  grep -q "Motor Control SDK Team" "$f" || echo "$f"
done
```

---

## Rule 0 — Vendor Files Are Out of Scope for Style Rules

Do not raise a naming/style finding against any file matching the vendor
category above. ST's MCSDK uses its own internally-consistent conventions
(Hungarian-notation locals like `hMFTaskCounterM1`, `MC_APP_`-prefixed public
hooks, MISRA C:2012 `//cstat` suppression comments) that predate this project
and must not be changed to match project-local rules. See
[CodeDesignRules.md](CodeDesignRules.md) Rule 1 for the immutability rule
itself (an architecture rule, not a style rule).

---

## Rule 1 — Function Naming: plain `lower_snake_case`

### 1.1 What to check

Every function in a fully-custom file (currently `motor_telemetry_math.c/h`)
uses plain `lower_snake_case`, no component prefix.

**How this was verified:** `Inc/motor_telemetry_math.h` — every declared
function (`speed_unit_to_rpm`, `s16_angle_to_degrees`, `counts_to_milliamps`,
`current_magnitude_milliamps`, `are_offsets_within_expected_range`) follows
this pattern with zero exceptions found.

### 1.2 Exception — overriding a vendor `__weak` hook

If custom code overrides an ST-declared `__weak` function (e.g. `main.c`
overrides `R3_1_SwitchOnPWM`/`SwitchOffPWM`/`TurnOnLowSides` to keep DRV8316
`nSLEEP` high), the override **must** keep the exact vendor name and
signature. Do not rename — the linker resolves by symbol name, and MCSDK
calls the vendor name, not a project-chosen one.

### 1.3 How to verify

```bash
grep -oP '(?<=^)[a-zA-Z_][a-zA-Z0-9_]*(?=\s*\()' Src/motor_telemetry_math.c
```
Flag any name that is not `^[a-z][a-z0-9_]*$`, except a name that exactly
matches an existing vendor `__weak` declaration (search
`grep -rn "__weak" Src/ Inc/` for the current list before flagging).

### 1.4 XML category

`category="FunctionNaming"`

---

## Rule 2 — Include Guards: `#ifndef MODULE_NAME_H`, no `#pragma once`

### 2.1 What to check

Every `.h` file in scope starts with `#ifndef MODULE_NAME_H` /
`#define MODULE_NAME_H`, where `MODULE_NAME` is the filename (without
extension) upper-cased, and ends `#endif /* MODULE_NAME_H */`.

**How this was verified:** `Inc/motor_telemetry_math.h` uses
`MOTOR_TELEMETRY_MATH_H` (no trailing underscore — note this project's guard
style differs from some other orgs' `_H_` convention; match what's already
here, don't import a different house style). Confirmed zero uses of
`#pragma once` anywhere in `Src/`/`Inc/` (`grep -rl "pragma once" Src Inc`
returned nothing on 02-08-2026) — stay consistent with that.

### 2.2 XML category

`category="IncludeGuard"`

---

## Rule 3 — Doxygen Style for Custom Files: `@brief`/`@param`/`@return`

### 3.1 What to check

Custom files (`motor_telemetry_math.c/h`) document functions with
`@brief`, `@param`, `@return` — **not** ST's `@retval`, and not ST's full
`@file`/`@author`/`@attention`/license-block/`@addtogroup` structure.

**Why not copy ST's block format:** ST's header block asserts ST copyright
and SLA0044 licensing — reusing it verbatim on project-authored code would
misstate authorship. Keep custom-file documentation in the simpler
`@brief`/`@param`/`@return` form already used in `motor_telemetry_math.h`.

### 3.2 XML category

`category="DoxygenStyle"`

---

## Rule 4 — No Unexplained Magic Numbers in Custom Code

### 4.1 What to check

Numeric literals in `motor_telemetry_math.c` (or any future custom module)
that represent a physical/hardware quantity must either come from a named
parameter passed in by the caller (matching the existing pattern —
`rpm_unit_num`, `current_conv_factor` are passed in, not hardcoded) or be
named as a local constant with a comment stating the unit and source.

### 4.2 How to verify

Review each numeric literal in the file; confirm it is either a parameter,
a `0`/`1`/simple loop bound, or has an adjacent comment naming its unit and
origin.

### 4.3 XML category

`category="MagicNumber"`

---

## Execution Loop

1. Recompute the vendor/custom file split (Scope section) — do not use a
   stale list.
2. Apply Rules 1–4 only to files in the "fully custom" and "`USER CODE`
   blocks only" categories.
3. Skip vendor files entirely (Rule 0).
4. Write findings to `codeRules/reports/CodeQualityReport.md` and
   `codeRules/reports/CodeQualityErrors.xml` (see
   [CodeDesignRules.md](CodeDesignRules.md) for the shared report format).
