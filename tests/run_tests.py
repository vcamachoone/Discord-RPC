#!/usr/bin/env python3
"""
run_tests.py - Master E2E Test Runner for Discord RPC Redesign

Executes all 4 tiers of the comprehensive test suite:
  - Tier 1: Feature Coverage (60 tests)
  - Tier 2: Boundary & Corner Cases (60 tests)
  - Tier 3: Cross-Feature Interactions (14 tests)
  - Tier 4: Real-World Application Scenarios (5 tests)

Exit code semantics:
  0: All executed tests passed cleanly (skips for pending milestones permitted)
  1: One or more test failures or unhandled errors encountered
"""

import argparse
import os
import sys
import time
import unittest
import warnings

# Suppress known harmless pypresence ResourceWarnings in Python 3.9
warnings.filterwarnings("ignore", category=ResourceWarning)

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ANSI Color Codes
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RESET = "\033[0m"


class TierResult:
    def __init__(self, name: str, suite_module: str):
        self.name = name
        self.suite_module = suite_module
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.skipped = 0
        self.duration = 0.0
        self.failures_list = []


def run_tier(tier_name: str, module_name: str, verbose: bool = False) -> TierResult:
    result = TierResult(tier_name, module_name)
    loader = unittest.TestLoader()

    try:
        suite = loader.loadTestsFromName(module_name)
    except Exception as e:
        print(f"{RED}[ERROR] Failed to load {module_name}: {e}{RESET}")
        result.errors = 1
        return result

    result.total = suite.countTestCases()

    start_time = time.time()
    runner = unittest.TextTestRunner(
        verbosity=2 if verbose else 1,
        stream=open(os.devnull, "w") if not verbose else sys.stdout,
    )
    test_res = runner.run(suite)
    result.duration = time.time() - start_time

    result.failed = len(test_res.failures)
    result.errors = len(test_res.errors)
    result.skipped = len(test_res.skipped)
    result.passed = result.total - result.failed - result.errors - result.skipped
    result.failures_list = test_res.failures + test_res.errors

    return result


def print_banner():
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║            Discord RPC League of Legends macOS - E2E Test Runner            ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{RESET}\n")
    print(f"  Project Root : {PROJECT_ROOT}")
    print(f"  Python Path  : {sys.executable}")
    print(f"  Architecture : macOS PyObjC Cocoa + Discord IPC Concurrency Actor")
    print(f"  Timestamp    : {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")


def print_tier_summary(r: TierResult):
    status_color = GREEN if (r.failed == 0 and r.errors == 0) else RED
    status_text = "PASS" if (r.failed == 0 and r.errors == 0) else "FAIL"

    print(f"  {BOLD}{r.name}{RESET}")
    print(f"    Module   : {r.suite_module}")
    print(f"    Status   : {status_color}{status_text}{RESET}")
    print(f"    Results  : {BOLD}{r.passed}{RESET} passed, {YELLOW}{r.skipped}{RESET} skipped, {RED}{r.failed + r.errors}{RESET} failed / {BOLD}{r.total}{RESET} total")
    print(f"    Duration : {r.duration:.3f}s\n")

    if r.failures_list:
        print(f"    {RED}--- Failures in {r.name} ---{RESET}")
        for test, err in r.failures_list:
            print(f"    {RED}• {test}{RESET}")
            lines = err.strip().split("\n")
            for line in lines[-3:]:
                print(f"      {line}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Run Discord RPC Redesign E2E Tests")
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run only the specified tier (1, 2, 3, 4, or 5)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose test execution output"
    )
    args = parser.parse_args()

    print_banner()

    tiers_to_run = [
        ("Tier 1: Feature Coverage", "tests.test_tier1_features"),
        ("Tier 2: Boundary & Corner Cases", "tests.test_tier2_boundaries"),
        ("Tier 3: Cross-Feature Interactions", "tests.test_tier3_interactions"),
        ("Tier 4: Real-World Scenarios", "tests.test_tier4_scenarios"),
        ("Tier 5: Adversarial Stress & Faults", "tests.test_adversarial_stress"),
    ]

    if args.tier:
        tiers_to_run = [tiers_to_run[args.tier - 1]]

    results = []
    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_skipped = 0
    total_tests = 0
    total_duration = 0.0

    print(f"{BOLD}Executing Test Suites...{RESET}\n")

    for tier_name, module_name in tiers_to_run:
        r = run_tier(tier_name, module_name, verbose=args.verbose)
        results.append(r)
        total_passed += r.passed
        total_failed += r.failed
        total_errors += r.errors
        total_skipped += r.skipped
        total_tests += r.total
        total_duration += r.duration
        print_tier_summary(r)

    # Final Summary Table
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}FINAL TEST SUITE SUMMARY{RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"  {'Tier Name':<38} {'Total':>7} {'Pass':>7} {'Skip':>7} {'Fail':>7} {'Time':>8}")
    print(f"  {'-'*38} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*8}")

    for r in results:
        print(f"  {r.name:<38} {r.total:>7} {r.passed:>7} {r.skipped:>7} {r.failed + r.errors:>7} {r.duration:>7.3f}s")

    print(f"  {'-'*38} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*8}")
    print(f"  {BOLD}{'TOTAL':<38} {total_tests:>7} {total_passed:>7} {total_skipped:>7} {total_failed + total_errors:>7} {total_duration:>7.3f}s{RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════════════════════════════{RESET}\n")

    if total_failed == 0 and total_errors == 0:
        print(f"{BOLD}{GREEN}✓ ALL EXECUTED TESTS PASSED CLEANLY (100% SUCCESS){RESET}")
        print(f"  Progressive milestone verification satisfied. Pending milestones cleanly skipped.\n")
        return 0
    else:
        print(f"{BOLD}{RED}✗ TEST SUITE FAILED WITH {total_failed + total_errors} ERRORS/FAILURES{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
