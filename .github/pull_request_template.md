### CNR Motor Driver Pull Request Checklist

<!--
  Adapted from the Vascular Sensor Firmware (i.MXRT1050) PR checklist for the
  CNR-Motor-Driver-1.0 project (STM32G431, ST Motor Control SDK + CubeMX).
  Reviewer names were replaced with generic role labels - fill in actual
  names/handles per PR, or edit this template once your Motor Driver review
  roster is fixed.
-->

### Code (Code Reviewer: _______________)
- [ ] Code review completed, including compliance with [CodeQualityRules.md](../CNR-Motor-Driver-1.0/codeRules/CodeQualityRules.md) and [CodeDesignRules.md](../CNR-Motor-Driver-1.0/codeRules/CodeDesignRules.md)
- [ ] `code-review` CI job (`codeRules/tools/code_quality_checker.py`) passed with no Blocking findings
- [ ] Compiler errors/warnings clean (ARM GCC build)
- [ ] SonarQube Cloud analysis passed
  - [ ] Security
  - [ ] Reliability
  - [ ] Maintainability
- [ ] No ST Motor Control SDK (vendor) file hand-edited outside a `USER CODE BEGIN/END` block
- [ ] Any override of a vendor `__weak` hook keeps the exact vendor name/signature and has a comment explaining why
- [ ] Doxygen: no critical errors/warnings, `@brief`/`@param`/`@return` present on new/changed custom-code functions

### Testing (Test Reviewer: _______________)
- [ ] Build succeeds (CMake/Ninja, Debug and Release presets)
- [ ] Unit tests (Unity, host build under `unit_tests/`) pass
- [ ] New/changed custom logic has positive, negative, and boundary-case unit tests
- [ ] Coverage report reviewed (currently report-only, no minimum-% gate)
- [ ] If this PR changes telemetry/diagnostic math in `main.c` or `motor_telemetry_math.c`, confirmed the other file's formulas still match (or documented why they now diverge)

### Design and Architecture (Design Reviewer: _______________)
- [ ] Compliance with [CodeDesignRules.md](../CNR-Motor-Driver-1.0/codeRules/CodeDesignRules.md) (vendor-file boundary, CubeMX `USER CODE` boundary, `motor_telemetry_math.c/h` staying MCSDK/HAL-independent)
- [ ] Design review completed

### Documentation (Documentation Reviewer: _______________)
- [ ] Doxygen documentation adequate for new/changed modules
- [ ] `sonar-project.properties` / CI workflow docs updated if build steps or source layout changed

### Pull Request Reviews (Approver: _______________)
- [ ] All reviews requested, done, and closed with approvals
