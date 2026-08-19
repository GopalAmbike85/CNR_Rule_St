> **Reference document - not enforced on this project.**
> This is the C Coding Guidelines document from the Vascular Sensor Firmware
> project (NXP i.MXRT1050, from-scratch Module/Component architecture). It is
> kept here for reference only, brought over on 16-08-2026 while setting up
> the CNR-Motor-Driver-1.0 (STM32G431) review process.
>
> **It does not apply to this codebase as-is.** CNR-Motor-Driver-1.0 is ~80%
> ST Motor Control SDK + STM32CubeMX-generated code, with one small
> hand-written module. Its actual, source-verified naming/style rules are in
> [../../codeRules/CodeQualityRules.md](../../codeRules/CodeQualityRules.md)
> (plain `lower_snake_case`, no `Prefix_moduleSuffix` scheme, vendor files
> out of scope) - that file is the source of truth for this project, not
> the document below.

---

# C Coding Guidelines (Embedded Focus)

This document defines coding style, header/API conventions, build rules, and test expectations for the Embedded C firmware projects.

## 0. Project References (Source of Truth)

Use these references together with this coding guide:
* **Design rules:** `DesignGuidelines.md` (Contains approved Component and Module Type suffix registries)

### 0.1 Public rule baselines
* **SEI CERT C Coding Standard:** Design and safety baseline for Embedded C.
* **Barr Group Embedded C Coding Standard:** Naming and readability reference (adapted for this project's specific architectural requirements).
* **Doxygen documentation standard:** `@file`, `@ingroup`, `@brief`, parameter directions.

### 0.2 Tools to set and check rules
* **Formatting:** `clang-format` based on Linux Kernel style (single source of truth via `.clang-format`).
* **Lint/static checks:** `clang-tidy` (readability-focused checks) and Custom Python Script (mandatory for architectural prefix/suffix validation).
* **Tests:** Standard C testing framework for unit and component tests.
* **Coverage:** `gcov`/`lcov` and CI guardrails.

## 1. Naming Conventions

### 1.1 Files
* Header/source pairs must use matching base names formatted as `Prefix_moduleSuffix.[c/h]`.
* The `Prefix` must match the approved Component list (`UpperCamelCase`). The `moduleSuffix` must be strictly `lowerCamelCase`.

### 1.2 Types and functions
* **Structs & Typedefs:** All structures must be defined using `typedef`. Custom struct typedefs must follow the `Prefix_lowerCamelCase_t` format.
* **Enums:** Values must utilize the Component prefix (`UpperCamelCase`) followed by `lowerCamelCase`.
* **Public Functions:** Must be formatted as `PrefixModuleSuffix_lowerCamelCaseAction`. Combine the Component prefix and the capitalized Module suffix, followed by an underscore, followed by the action verb.
* **Sensible Shortening:** Unit names must remain descriptive but shortened sensibly to prevent excessive length.
* **Static/Private Functions:** Must be formatted strictly as `lowerCamelCase` (action only). The prefix/module combination is strictly prohibited.

### 1.3 Local variable rules
* Local variables must be descriptive and use `lowerCamelCase`.
* **Units:** Variables representing measured/physical values or time must include a unit suffix (e.g., `timeoutMs`, `voltageMv`).
* **Single-letter names:** (`x`, `y`, `i`) are strictly prohibited, allowed only if they directly map to a standard mathematical formula or short loop index.
* Keep local variable scope as small as possible (declare near first use).
* **Initialization:** All local variables must be initialized at the point of declaration. Uninitialized local variables are prohibited.

### 1.4 Constants and macros
* **Macros:** Must be strictly `UPPER_SNAKE_CASE` and include both the Component prefix and the Module suffix (converted to uppercase) to guarantee traceability.

## 2. Header and API Rules

### 2.1 Header hygiene
* Standard `#ifndef` include guards must be used to prevent multiple inclusions (e.g., `#ifndef PREFIX_MODULESUFFIX_H`). The use of `#pragma once` is strictly prohibited.
* **Include only what is strictly required.** To prevent circular dependencies, header files must not include other header files unless absolutely necessary for a `typedef`.
* `component_common.h` files must ONLY contain `typedef`s, global variable `extern` declarations, and macros. No API declarations are permitted here.

### 2.2 Public/private boundaries
* **Public Interfaces:** API prototypes for a specific module must be centralized in its dedicated header (`Prefix_moduleSuffix.h`).
  * **Anti-Nesting Rule:** Module headers must never `#include` other module headers. If a `.c` file needs to call another module's public function, the `.c` file itself must `#include` that specific header.
* **Private/Static Interfaces:** All static function declarations must reside in a dedicated static header (`Prefix_moduleSuffixStatic.h`).
* Do not expose private helper APIs in public module headers.

### 2.3 Global state & memory
* **Context Structs:** Module state must be encapsulated within a context structure. Units requiring state memory must accept a pointer to this instance.
* **Global Variables:** True global variables must be defined exclusively in `main.c` and declared using `extern` at the top of the consuming `.c` files.

### 2.4 Internal function interface rules
* Internal functions must pass input and output through function arguments. Relying on global variables for hidden data flow is strictly prohibited.
* **Output values:** Should be returned via output pointers placed at the absolute end of the parameter list.
* **Read-only inputs:** Any input pointer that is strictly read-only must be marked as `const`.
* **Return values:** Function return values must represent execution status (e.g., success, failure, error code), not business payload.
* **Return value checking:** Every call to a function that returns a status value must either check the result (e.g., `if (0 != result)`) or explicitly discard it with a `(void)` cast. Silently ignoring a status return is prohibited.
* **Memory operation bounds:** Size arguments to `memcpy`, `memset`, and all buffer-write operations must not exceed the destination buffer's declared size. The size argument must be bounded by the destination — never derived from the source alone.
* **Arithmetic narrowing:** Any assignment that narrows the numeric range (e.g., `uint32_t` to `uint8_t`, `float` to `int32_t`) must be preceded by an explicit range check. Silent truncation is prohibited.

### 2.5 Control flow restrictions
* `goto` is prohibited in all production source files. No exceptions.

### 2.6 Function complexity
* The cyclomatic complexity of any function must not exceed 10. A function exceeding this threshold is a blocking GL Review finding. Decompose into smaller named helpers.

### 2.7 Duplicated logic
* A block of 3 or more consecutive identical statements must not be repeated in more than one location. Duplicated logic must be extracted into a named helper function.

## 3. Doxygen Rules

### 3.1 File and API headers
* Doxygen blocks documenting a unit's purpose and parameters must reside **exclusively** in the `.h` or `Static.h` files.
* Inside `.c` files, Doxygen is permitted *only* for explaining internal algorithms using the `@details` tag.

### 3.2 Function docs
Use explicit parameter direction:
* `@param[in]`
* `@param[out]`
* `@param[in,out]`
* `@retval` (Detailed explanation of execution status returned)

### 3.3 Group consistency
* Use component group names consistently via the `@ingroup` tag, mapping to the project's functional hierarchy.

## 4. Automated Tooling & Formatting

### 4.1 Code Formatting
* All C code must be formatted using `clang-format`.
* Aesthetic rules (indentation, spaces, line wrapping, parenthesis alignment) are strictly governed by the `.clang-format` file located in the repository root, utilizing the **Linux Kernel** style as the baseline.

### 4.2 Architecture validation
* Due to the strict `PrefixModuleSuffix_lowerCamelCaseAction` requirements, standard linting tools cannot natively parse the architectural dictionary. A custom **Python + rule-based script** runs in the CI/CD pipeline to validate all architectural naming rules.

## 5. Testing Rules

### 5.1 Test layers
* **Component tests:** Focus on the interaction between multiple Modules within the same Component.
* **Unit tests:** Focus on the lowest level of testable code (a single Unit/function).

### 5.2 Mock policy
* Mock external dependencies only (Hardware interfaces, RTOS primitives, external components).
* Keep internal business logic real in component tests.
* In unit tests, isolate the unit under test and mock all non-owned collaborators.

### 5.3 Mandatory unit test coverage style
For each unit-tested function, include:
* **Positive tests** (expected valid inputs/flows)
* **Negative tests** (invalid/error flows, null pointer handling, timeout states)
* **Range/boundary tests** (min/max/edge values, array limits)

### 5.4 Test coverage target
* Overall tests should target 100% code coverage for the selected unit scope, including branch/path coverage where feasible.

### 5.5 Testability hooks
* Use `UNIT_TEST` macros only when needed.

### 5.6 Coverage guardrails
* CI/scripts should fail when branch coverage summary is missing or zero.

## 6. Lightweight Review Checklist

* [ ] **Automated Formatting:** Code processed by `clang-format` and complies with `.clang-format` (Linux Kernel baseline).
* [ ] **Python Validation:** Custom script passes with zero naming architecture violations.
* [ ] **Boundaries:** API prototypes are strictly in `Prefix_moduleSuffix.h`; Static APIs in `Prefix_moduleSuffixStatic.h`. Headers do not include other headers.
* [ ] **Data Flow:** Inputs/outputs strictly via arguments (`const` for inputs). No payload via return values.
* [ ] **Variable Naming:** No single-character variables (`x`, `y`) unless part of strict math formula. Physical values have unit suffixes.
* [ ] **Variable Initialization:** All local variables initialized at declaration. No uninitialized locals.
* [ ] **Macro Naming:** Macros include Module suffix and are strictly `UPPER_SNAKE_CASE`.
* [ ] **Type Definitions:** All structures are defined using `typedef`.
* [ ] **Return value checking:** Every status-returning call is checked or explicitly discarded with `(void)`. No silently ignored status returns.
* [ ] **No goto:** No `goto` in any production source file.
* [ ] **Function complexity:** No function exceeds cyclomatic complexity 10.
* [ ] **No duplicated logic:** No block of 3+ consecutive identical statements repeated in more than one location.
* [ ] **Documentation:** Doxygen parameter tags explicitly denote `[in]`, `[out]`. Blocks reside in header files.
* [ ] **Testing:** Unit tests include positive/negative/range cases with relevant mocks applied.
