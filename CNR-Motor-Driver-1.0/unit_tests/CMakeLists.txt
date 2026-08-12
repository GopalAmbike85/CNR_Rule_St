# ─── unit_tests/CMakeLists.txt (v1) ─────────────────────────────────────────
# Purpose : Host-side build (plain gcc, no ARM toolchain) for the Unity tests
#           under unit_tests/test/. Deliberately a SEPARATE CMake project from
#           the top-level CNR-Motor-Driver-1.0/CMakeLists.txt, which is fixed
#           to the arm-none-eabi cross toolchain and cannot produce a runnable
#           host binary.
# Date    : 12-08-2026
#
# Only host-testable sources (see CodeQualityRules.md scope table - currently
# just motor_telemetry_math.c/.h) are compiled here. Vendor/MCSDK/HAL code
# needs real hardware or heavy mocking and is out of scope for this target.
#
# Unity is fetched at configure time (ThrowTheSwitch/Unity, tag v2.7.0 -
# confirmed the latest tag on github.com/ThrowTheSwitch/Unity as of this
# date) rather than vendored, since it is test-only tooling, not firmware
# source. Requires network access at configure time (present on GitHub
# Actions runners).
#
# Usage:
#   cmake -S unit_tests -B unit_tests/build -G Ninja
#   cmake --build unit_tests/build
#   ctest --test-dir unit_tests/build --output-on-failure
# ─────────────────────────────────────────────────────────────────────────────

cmake_minimum_required(VERSION 3.14)  # FetchContent_MakeAvailable requires 3.14+

project(cnr_motor_driver_unit_tests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

include(FetchContent)

FetchContent_Declare(
    unity
    GIT_REPOSITORY https://github.com/ThrowTheSwitch/Unity.git
    GIT_TAG        v2.7.0
)
FetchContent_MakeAvailable(unity)

# Firmware root, i.e. CNR-Motor-Driver-1.0/
set(FW_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/..)

add_executable(motor_telemetry_math_tests
    test/test_motor_telemetry_math.c
    ${FW_ROOT}/Src/motor_telemetry_math.c
)

target_include_directories(motor_telemetry_math_tests PRIVATE
    ${FW_ROOT}/Inc
)

target_link_libraries(motor_telemetry_math_tests PRIVATE unity)

if(NOT WIN32)
    # motor_telemetry_math.c uses sqrtf() (math.h); on Linux this needs
    # explicit linking against libm.
    target_link_libraries(motor_telemetry_math_tests PRIVATE m)
endif()

# --coverage enables gcov instrumentation on GCC/Clang. Harmless if unused -
# the .gcda/.gcno files are simply not consumed unless something (gcovr)
# processes them, which CI does; see cnr_review_test_coverage.yml.
target_compile_options(motor_telemetry_math_tests PRIVATE -O0 -g --coverage)
target_link_options(motor_telemetry_math_tests PRIVATE --coverage)

enable_testing()
add_test(NAME motor_telemetry_math_tests COMMAND motor_telemetry_math_tests)
