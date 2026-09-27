# E2E Test Infra: Discord RPC macOS Redesign

## Test Philosophy
- Opaque-box, requirement-driven verification derived directly from ORIGINAL_REQUEST.md.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Interaction + Real-World Workload Testing.
- Executed independently of UI visual inspection using headless AppKit verification, mock socket tests, and network validation.

## Feature Inventory & Test Mapping
| # | Feature | Requirement | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) |
|---|---|---|:---:|:---:|:---:|
| F1 | Dynamic Menubar Icons | R2 | 5 | 5 | ✓ |
| F2 | Menu Bar Item (NSStatusItem) | R1 | 5 | 5 | ✓ |
| F3 | Floating Dark NSPopover UI | R1 | 5 | 5 | ✓ |
| F4 | Interactive Mode Selector | R1 | 5 | 5 | ✓ |
| F5 | Interactive Switches | R1 | 5 | 5 | ✓ |
| F6 | Bottom Action Button | R1 | 5 | 5 | ✓ |
| F7 | Settings / Detailed View | R3 | 5 | 5 | ✓ |
| F8 | Champion Resolver & Data Dragon | R3 | 5 | 5 | ✓ |
| F9 | Rank Crests & Division Formatter | R3 | 5 | 5 | ✓ |
| F10 | Concurrency & Thread-Safe RPC Manager | R4 | 5 | 5 | ✓ |
| F11 | Auto-restart Match Timer | R1 | 5 | 5 | ✓ |
| F12 | App Bundle Packaging & Sync | R4 | 5 | 5 | ✓ |

## Test Architecture
- Test Runner: `/Users/victormanuel/discord-rpc/tests/run_tests.py`
- Test Directory: `/Users/victormanuel/discord-rpc/tests/`
- Exit Code Semantics: Exit 0 on 100% pass, non-zero on any failure.
- Test Output: Formatted progress and summary per tier.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|---|---|---|
| S1 | Official Mode Full Lifecycle: App starts, connects to Discord, toggles paused and resumed, triggers 20-min match reset | F1, F2, F3, F4, F6, F10, F11 | High |
| S2 | Detailed Mode Riot Champion Selection: User types special champion "wukong", rank "Challenger", verifies valid CDN and division suppression | F4, F7, F8, F9, F10 | High |
| S3 | Concurrency Stress Test: Rapid button clicks and setting toggles do not crash event loop or block UI runloop | F4, F5, F6, F10 | High |
| S4 | Network/Discord Disconnect & Reconnect: Discord IPC socket abruptly closes, manager handles BrokenPipe cleanly, reconnects when socket re-opens | F1, F6, F10 | High |
| S5 | App Bundle Integrity & Launch: /Applications bundle Info.plist, executable permissions, and resource synchronization verified | F12 | Medium |

## Coverage Thresholds
- Tier 1: >= 5 test cases per feature (60+ tests)
- Tier 2: >= 5 test cases per feature for boundaries & error cases (60+ tests)
- Tier 3: Pairwise combinations across major features (12+ tests)
- Tier 4: >= 5 application scenarios (5 tests)
- Total target: ~140 tests
