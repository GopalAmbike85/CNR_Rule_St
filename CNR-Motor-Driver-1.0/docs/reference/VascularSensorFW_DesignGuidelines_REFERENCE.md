> **Reference document - not enforced on this project.**
> This is the C Design Guidelines document from the Vascular Sensor Firmware
> project (NXP i.MXRT1050, from-scratch Module/Component architecture with
> its own thread/driver/utils layering). Kept here for reference only,
> brought over on 16-08-2026 while setting up the CNR-Motor-Driver-1.0
> (STM32G431) review process.
>
> **It does not apply to this codebase as-is.** CNR-Motor-Driver-1.0 is built
> almost entirely on ST's Motor Control SDK plus STM32CubeMX-generated glue,
> not a from-scratch layered architecture. Its actual, source-verified
> architecture rules (vendor-file immutability, `USER CODE` boundaries,
> `motor_telemetry_math.c/h` HAL-independence, etc.) are in
> [../../codeRules/CodeDesignRules.md](../../codeRules/CodeDesignRules.md) -
> that file is the source of truth for this project, not the document below.

---

# C Design Guidelines (Embedded Focus)

This document defines architecture and design rules for the Embedded C firmware projects. It mirrors the C++ Design Guidelines, adapting Object-Oriented principles to C firmware realities. There are a few altercations specifically for Vascular Sensor Firmware and they are duly mentioned

## 1. Scope and Folder Conventions

### 1.1 App layout
Ideally, new C applications should follow the standard organizational layout (mirrored from the apps):
- `inc/` public concrete headers
- `intf/` abstract interfaces (or hardware abstraction definitions in C)
- `src/` implementations (`*.c`)
- `tests/component/` component tests and mocks
- `tests/unit/` unit tests

**Exception for Vascular Sensor Firmware:** The Vascular Sensor Firmware project follows a **Module-first, Component-second** hierarchy within the root `application/` folder:
* **Module Type Folders:** Categorized by logical purpose (e.g., `application/utils/`, `application/driver/`, `application/systemThreads/`).
* **Component Subfolders:** Inside the module folder, code is grouped by component (e.g., `application/utils/Pid_utils/`, `application/utils/Pn_utils/`).
* **File Hierarchy:** Each component subfolder must contain:
  * `Prefix_moduleSuffix.c` (Implementation)
  * `Prefix_moduleSuffix.h` (Public API header)
  * `Prefix_moduleSuffixStatic.h` (Private/Static header)
  * `tests/` (Unit and component tests)

### 1.2 Common modules
*Note: This specific cross-application shared library concept from the C++ guidelines is not required for the monolithic C firmware project.*

Shared utility logic must reside in standard `utils/` modules.

### 1.3 One responsibility per class
*In C, this applies to the Component level.*

A Component (e.g., Pneumatics, Telemetry) should have one reason to change and one distinct responsibility.
* Do not mix domain logic. UI rendering logic must never bleed into a hardware driver.
* Inside a Component, responsibilities are split by module type (e.g., `_thrd` handles the RTOS loop, `_drv` handles bare-metal registers).

## 2. Dependency and Layering Rules

### 2.1 Interface-first dependencies
*In C, this translates to strict Hardware Abstraction Layering.*

To decouple application logic from external hardware, depend on layers:
* Threads (`_thrd`) **must never** call HAL APIs or manipulate hardware directly.
* Threads must depend on Utilities (`_utils`) for business logic and sequences.
* Low-level hardware access is strictly isolated to Drivers (`_drv`).

### 2.2 Composition in `main.cpp`, behavior in services
*In C, this translates to `main.c` and threads/utils.*
* `main.c` composes the system: it defines true global variables, runs core hardware initialization, and spawns RTOS threads.
* Threads and Utilities hold the behavior and lifecycle decisions. Individual modules should not define their own hidden global execution threads.

### 2.3 Constructor injection only
*Since C does not have classes/constructors, this is achieved via Context Pointer Injection.*
* Required state memory and dependencies must be passed explicitly as function arguments (e.g., passing a pointer to a Context Struct).
* Avoid hidden global singletons and static mutable state for cross-module communication.

### 2.4 Keep wrappers thin
Classes (or in C, Driver modules `_drv` and HAL wrappers) should adapt external frameworks/hardware to the application and must **not** include domain logic, state machines, or complex medical business rules.

## 3. D-Bus and Constants

### 3.1 Central constants
*Note: D-Bus is not applicable to the C firmware project, but the centralization rule applies to hardware configuration.*
* Hardware-specific constants (GPIO pins, ADC channels, I2C addresses) must be centralized in the `systemConfigs/` folder.
* The use of "magic numbers" embedded directly in logic is strictly prohibited. Use `enum` for states/options and `#define` for physical limits.

### 3.2 Registration pattern
*Note: D-Bus registration is not applicable/required for the C project.*

## 4. Error-Handling Design

### 4.1 Explicit result contracts
* Use clear execution status contracts. Every unit (function) must return a value indicating execution status (success, failure, error code).
* Returning operational data via the function's return parameter is strictly prohibited. Output data must be passed via pointers at the end of the argument list.

### 4.2 Validation-first
Validate external input early (raw ADC readings, sensor communication statuses, UART payloads, OTA packets) and fail clearly if data is out of physical or mathematical bounds. Do not let corrupted data propagate.

### 4.3 Observable failures
Use the centralized `Log` utility to log actionable failures with context (e.g., driver initialization failures, queue timeouts). No silent failures.

## 5. Testability by Design

### 5.1 Design for isolation
* Business logic modules (`_utils`) should be testable without real RTOS or bare-metal hardware dependencies.
* Use Context Structs and explicit arguments to isolate external modules.

### 5.2 Unit vs component intent
* `tests/unit`: verify function behavior in isolation, high branch/path coverage.
* `tests/component`: verify collaboration wiring and behavior with internal modules real and external modules mocked.

### 5.3 Test depth expectations
For `tests/unit`, include:
* Positive tests
* Negative tests
* Boundary/range tests (`min`, `max`, `invalid`, `empty`, overflow-like values)

Target: 100% code coverage for selected unit scope, including branch coverage where practical.

## 6. Anti-patterns (Do Not Do)

* Hardcoding hardware pins or magic numbers directly in logic files.
* Threads (`_thrd`) making direct HAL or bare-metal register calls.
* New global mutable state for cross-class/cross-module communication.
* Exposing private/static functions in public module headers.

## 7. SQL Database Design Rules
*Note: This entire section (7.1 through 7.8) is not applicable to the embedded C firmware project.*

---

## 8. C-Specific: Nomenclature & Architectural Hierarchy
* **Component Prefixes:** Every component is assigned a specific `UpperCamelCase` prefix (2 to 6 alphanumeric characters). All-uppercase prefixes are strictly prohibited except for Macros.
* **Module Type Suffixes:** Developers must use predefined Module Type suffixes appended to the Component prefix (e.g., `Pn_utils`).

**Approved Suffixes:** `thrd` (Threads), `utils` (Utilities), `isr` (Interrupts), `drv` (Drivers), `scr` (UI Screens), `widg` (UI Widgets), `stmach` (State Machine).

## 9. C-Specific: Header File Architecture
* **Public APIs:** Declarations must be centralized in their specific module header (e.g., `Pn_utils.h`).
* **Static APIs:** Private declarations must be placed in a static header (e.g., `Pn_utilsStatic.h`).
* **`component_common.h`:** Must ONLY contain `typedef`s, global variable `extern` declarations, and macros. No API declarations allowed.

## 10. C-Specific: Doxygen Interface Enforcement
Doxygen blocks documenting parameters must reside exclusively in `.h` or `Static.h` files.
```c
/**
 * @fn [complete function name here]
 * @ingroup [Group hierarchy of the function, refer Annex D]
 * @brief [brief introduction of function]
 *
 * @param[in/out] [input/out parameter and its direction]
 * @retval    [detailed explanation of value being returned]
 */
```
Internal algorithm explanations are permitted inside `.c` files using the `@details` tag.

---
# ANNEXES: Component & Subcomponent Registries

### Annex A: Vascular Sensor (VS) Firmware Prefix Table
| Component / Subcomponent | Prefix | Description |
| :--- | :--- | :--- |
| Pneumatics | `Pn_` | Pneumatic controls, includes motor, valves, pressure sensors, ADC, DAC, IOExpander etc. |
| PID Controller | `Pid_` | Closed-loop control subcomponent of Pn, generates DAC values to control motor, valve. |
| Data Acquisition | `Das_` | ADC reading for pressure sensor, raw data management. |
| Telemetry | `Toe_` | Communication Module, ESP32 based, responsible for external world communication over WiFi. |
| Updater | `Ota_` | Responsible for providing over-the-air updates. |
| Test Script Parser | `Tsp_` | Parses Exam parameters from files stored in memory. |
| UI | `Ui_` | User interface managing LVGL display, touch, screens, widgets, and state machine. |
| Occlusion | `Occ_` | Subcomponent of DAS; detects occlusion to control Pneumatics. |
| File System / FAT | `Fs_` | Subcomponent of DAS for storage or reading. |
| RTC | `Rtc_` | Real-time clock for time keeping. |

### Annex B: Bootloader Prefix Table
*(To be populated with Bootloader specific components/subcomponents)*

### Annex C: OscBp Prefix Table
| Component | Prefix | Description |
| :--- | :--- | :--- |
| Oscillometric BP | `OscBp_` | Blood pressure calculation algorithms. |

### Annex D: Vascular Sensor Functional Hierarchy (for doxygen)
| Parent | Primary Child | Secondary Child | Comments |
| :--- | :--- | :--- | :--- |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-UI` | UI thread is under thread, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-DASThread` | DAS thread is under thread, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-TS` | Touch Screen thread is under thread, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-Telemetry` | Telemetry (communication) thread is under thread, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-Occ` | Occlusion thread is under thread, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-MonitorIOExpander` | Monitor IO Expander thread is under thread, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-RTC` | RTC thread is under thread, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-OLBtn` | Overlay Button thread is under thread, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Threads` | `VSFW-Threads-FactoryReset` | Factory Reset thread is under thread, which is under Vascular Sensor Firmware *(planned — no `@defgroup` in CommonExtern.h yet)* |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-RTC` | RTC Driver is under Drivers, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-ADC` | ADC for Pressure sensor Driver is under Drivers, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-DAC` | DAC for motor and valve Driver is under Drivers, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-IOEX` | IOExpander Driver is under Drivers, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-USBMSD` | USBMSD Driver is under Drivers, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-USBHOSTSTACK` | USBHostStack Driver is under Drivers, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-LVGL` | LVGL Driver is under Drivers, which is under Vascular Sensor Firmware *(planned — no `@defgroup` in CommonExtern.h yet)* |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-NORFlash` | NORFlash Driver is under Drivers, which is under Vascular Sensor Firmware *(planned — no `@defgroup` in CommonExtern.h yet)* |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-TCHPanel` | Touch Panel Driver is under Drivers, which is under Vascular Sensor Firmware *(planned — no `@defgroup` in CommonExtern.h yet)* |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-Telemetry` | Telemetry (ESP32 ToE) Driver is under Drivers, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-TRNG` | TRNG Driver is under Drivers, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Drivers` | `VSFW-Drivers-USDHC` | USDHC Driver is under Drivers, which is under Vascular Sensor Firmware *(planned — no `@defgroup` in CommonExtern.h yet)* |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-DAS` | DAS Utils is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-Log` | Log Utils is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-FS` | FS (FAT FS/File system) Utils is under Utils, which is under Vascular Sensor Firmware *(planned — no `@defgroup` in CommonExtern.h yet)* |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-PID` | PID Utils is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-Pn` | Pn Utils is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-ResultCalculation` | Result Calculations Utils is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-MMCUtils` | MMC (eMMC/FatFS file ops) Utils is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-Telemetry` | Telemetry HTTP Utils is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-Updater` | Firmware Updater (OTA download orchestration + flash apply) is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-Checksum` | Checksum primitives (CRC16) shared util is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-TestScriptParser` | Test-script/exam-config file parser is under Utils, which is under Vascular Sensor Firmware |
| VascularSensorFw | `VSFW-Utils` | `VSFW-Utils-DCP` | DCP crypto (AES-128-CBC token encrypt/decrypt via OTPMK) Utils is under Utils, which is under Vascular Sensor Firmware |
