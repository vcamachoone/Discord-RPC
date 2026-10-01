# Handoff Report — Milestone M8 Adversarial Review (Requirement R2: Discord Interactive Profile Buttons)

## Review Summary

**Verdict**: **APPROVE**

Milestone M8 fully satisfies Requirement R2 from `ORIGINAL_REQUEST.md` (§ Follow-up — 2026-09-29T23:10:58Z). Zero integrity violations were detected. All empirical stress tests for `sanitize_buttons()` edge cases pass, and the application strictly complies with Discord IPC schema constraints by completely omitting the `"buttons"` key when no valid buttons exist, preventing empty array (`[]`) transmission.

---

## 1. Observation

### 1.1 Integrity Audit
- Audited implementation in:
  - `/Users/victormanuel/discord-rpc/discord_rpc_manager.py` (lines 166–225, 287–302, 738–748, 770–840)
  - `/Users/victormanuel/discord-rpc/liquid_html.py` (lines 601–650, 860–895, 1479–1530, 1565–1590)
  - `/Users/victormanuel/discord-rpc/popover_ui.py` (lines 159–165, 217, 854, 915, 930, 1625–1680)
  - `/Users/victormanuel/discord-rpc/tests/test_milestone8_buttons.py`
- Integrity findings:
  - **No hardcoded test outputs or mock bypasses**: Logic dynamically parses, sanitizes, and verifies arbitrary inputs.
  - **No dummy or facade implementations**: Full functional implementation across backend actor, IPC payload generation, WebKit bridge, and Cocoa popover layout.
  - **No task bypasses**: Interactive button configuration is integrated into `#view-config` with glass styling, scrollbar support, live state synchronization, and persistence in `~/.config/lol_discord_rpc/config.json`.
  - **Genuine independent verification**: 100% genuine test execution across master runner, unit tests, and challenger stress suites.

### 1.2 Inspection of `sanitize_buttons()` Implementation
- In `/Users/victormanuel/discord-rpc/discord_rpc_manager.py` (lines 179–225):
  ```python
  def sanitize_buttons(raw_buttons: Any) -> Optional[List[Dict[str, str]]]:
      if not isinstance(raw_buttons, (list, tuple)):
          return None

      valid: List[Dict[str, str]] = []
      for item in raw_buttons:
          if not isinstance(item, dict):
              continue

          raw_label = item.get("label")
          raw_url = item.get("url")

          if raw_label is None or raw_url is None:
              continue

          label = str(raw_label).strip()
          url = str(raw_url).strip()

          if not label or not url:
              continue

          # Enforce HTTPS
          if url.startswith("http://"):
              url = "https://" + url[7:]
          elif not url.startswith("https://"):
              url = "https://" + url

          # Truncate label to 32 and url to 512
          label = label[:32]
          url = url[:512]

          valid.append({"label": label, "url": url})
          if len(valid) == 2:
              break

      return valid if valid else None
  ```

### 1.3 Inspection of RPC Payload Transmission (`_send_rpc_update`)
- In `/Users/victormanuel/discord-rpc/discord_rpc_manager.py` (lines 787–837):
  ```python
  valid_buttons = sanitize_buttons(buttons)
  ...
  # oficial mode
  kwargs: Dict[str, Any] = {
      "start": start_time,
      "large_image": LOL_LOGO_URL,
      "large_text": "League of Legends",
  }
  if valid_buttons is not None:
      kwargs["buttons"] = valid_buttons
  rpc.update(**kwargs)
  ...
  # detallado mode
  if valid_buttons is not None:
      kwargs["buttons"] = valid_buttons
  rpc.update(**kwargs)
  ...
  # other game presets
  if valid_buttons is not None:
      kwargs["buttons"] = valid_buttons
  rpc.update(**kwargs)
  ```
- **Empty Array Prevention**: When `valid_buttons is None`, the `"buttons"` key is completely omitted from `kwargs`. `pypresence`'s `update()` never receives an empty list (`[]`), avoiding Discord Gateway IPC schema rejection.

### 1.4 Test Suite Execution Results
1. **Master Test Runner** (`tests/run_tests.py`):
   - Command: `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
   - Output:
     ```text
     Tier 1: Feature Coverage            : 60 passed / 60 total
     Tier 2: Boundary & Corner Cases     : 60 passed / 60 total
     Tier 3: Cross-Feature Interactions  : 14 passed / 14 total
     Tier 4: Real-World Scenarios        : 5 passed / 5 total
     Tier 5: Adversarial Stress & Faults : 10 passed / 10 total
     TOTAL                               : 149 passed / 149 total (100% success)
     ```
   - Exit code: `0`.
2. **Milestone 8 Unit Suite** (`tests/test_milestone8_buttons.py`):
   - Command: `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_milestone8_buttons.py`
   - Output: `Ran 27 tests in 0.202s - OK`.
   - Exit code: `0`.
3. **Challenger Adversarial Stress Suites**:
   - Command: `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_challenger_m8_buttons.py tests/test_challenger_m8_stress.py`
   - Output: `Ran 31 tests in 0.191s - OK`.
   - Exit code: `0`.
4. **Lifecycle and Audit Fixes Suites**:
   - Command: `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_audit_fixes.py tests/test_challenger_audit_2.py tests/test_milestone7_lifecycle.py tests/test_adversarial_m7_challenger.py tests/test_challenger_m7_stress.py`
   - Output: `Ran 78 tests in 6.957s - OK`.
   - Exit code: `0`.
5. **Universal Test Discovery** (`-m unittest discover -s tests -p "test_*.py"`):
   - Output: `Ran 333 tests in 30.024s - FAILED (failures=1)`
   - Single failure: `test_challenger_06b_unhandled_non_dict_in_coalescer_defect_probe` in `tests/test_challenger_audit.py`.
   - Cause: This test was authored in Milestone M6 as an empirical demonstration probe asserting that the worker thread crashed (`self.assertTrue(worker_died)`). When defensive type checking (`if isinstance(payload, dict) and isinstance(next_payload, dict):`) was introduced, the worker thread no longer crashes on non-dict payloads. The failure is due to an inverted assertion in an obsolete defect probe, not a regression.

### 1.5 Application Bundle Synchronization
- Command: `/Users/victormanuel/discord-rpc/venv/bin/python sync_bundle.py`
- Result: Cleanly synchronized `discord_rpc_manager.py`, `popover_ui.py`, and `liquid_html.py` into `/Applications/League of Legends RPC.app/Contents/Resources/`.

---

## 2. Logic Chain

1. **Requirement R2 Fulfillment (Observation 1.2, 1.3)**:
   - Requirement R2 mandates:
     a) Up to two interactive clickable profile buttons configurable in `#view-config` (Label and URL).
     b) HTTPS enforcement and length validation (label <= 32, url <= 512).
     c) Dispatching the buttons cleanly to `pypresence` without crashing on empty or partial fields.
     d) Persistence between sessions in `~/.config/lol_discord_rpc/config.json`.
   - Code inspection verifies each component is implemented accurately and securely.
2. **Discord Gateway IPC Schema Conformance (Observation 1.3)**:
   - Discord's IPC API requires that if `"buttons"` is provided, it must be a non-empty array of length 1 or 2, with valid HTTPS URLs. Providing `[]` produces an IPC schema error and disconnects the RPC socket.
   - `sanitize_buttons()` returns `None` for empty arrays, whitespace-only fields, missing attributes, or non-dict items.
   - `_send_rpc_update()` conditionally adds `kwargs["buttons"]` only when `valid_buttons is not None`.
   - When no buttons are configured or all buttons are invalid, the `"buttons"` key is omitted entirely from `rpc.update(**kwargs)`.
   - When valid buttons exist, at most 2 items are included, each guaranteed to start with `https://` and respect length limits.
3. **Edge Case Resilience (Observation 1.2, 1.4)**:
   - Non-dict items (None, numbers, strings, nested lists) in the buttons list are discarded without exceptions.
   - Non-web schemes (`javascript:`, `file:`, `discord:`, `ftp:`) are prefixed with `https://`, neutralizing URI execution attacks.
   - Extremely long URLs (>1000 characters) are truncated to 512 characters.
   - Unicode labels and emojis are supported and capped at 32 characters.
4. **Master Test Suite Health (Observation 1.4)**:
   - All 149 master tests across Tiers 1–5 pass cleanly.
   - All 27 Milestone 8 unit tests pass cleanly.
   - All 31 Challenger stress tests pass cleanly.
   - The single failure in `tests/test_challenger_audit.py` is an obsolete probe asserting that a previously fixed bug still causes crashes; production code is strictly safer.

---

## 3. Findings

### Minor / Advisory Finding 1: Outdated Defect Probe in `test_challenger_audit.py`
- **What**: Test `test_challenger_06b_unhandled_non_dict_in_coalescer_defect_probe` fails during broad test discovery (`discover -s tests`).
- **Where**: `tests/test_challenger_audit.py:452–476`
- **Why**: The test asserts that passing `None` as a `CONFIG_CHANGE` payload crashes the worker thread (`self.assertTrue(worker_died)`). When defensive type checking was implemented in `discord_rpc_manager.py:617` (`if isinstance(payload, dict) and isinstance(next_payload, dict):`), the worker thread stopped crashing. The assertion now fails because the application is more resilient than the test expected.
- **Suggestion**: In Milestone M10 (Production Test Consolidation), update the assertion to verify that the worker thread *survives* (`self.assertTrue(mgr._worker_thread.is_alive())`).

---

## 4. Stress Test Results

| Attack / Edge Case Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| Non-dict items in button array (`[None, 123, "str", {}]`) | Discard invalid items, extract valid | Only valid dicts extracted, returns `None` if empty | PASS |
| Non-list primitives (`None`, `123`, `"abc"`, `{}`) | Return `None` cleanly | Returns `None` without exception | PASS |
| 3+ valid buttons provided (e.g. 5 or 10 buttons) | Truncate to first 2 buttons | Returns exactly 2 buttons | PASS |
| Missing label or missing URL key | Discard incomplete items | Discarded cleanly | PASS |
| Whitespace-only label or URL (`"   "`, `"\t\n"`) | Stripped to `""` and discarded | Discarded cleanly | PASS |
| Insecure HTTP URL (`http://op.gg`) | Upgraded to `https://op.gg` | Upgraded to `https://op.gg` | PASS |
| URL without scheme (`op.gg/summoner`) | Prefixed with `https://` | Normalized to `https://op.gg/summoner` | PASS |
| Non-web schemes (`javascript:alert(1)`, `file:///etc/passwd`) | Defanged by `https://` prefix | Normalized to `https://javascript:alert(1)` | PASS |
| Huge URL (>1000 characters) | Truncated to 512 characters | Truncated to 512 characters | PASS |
| Long label (>100 characters) | Truncated to 32 characters | Truncated to 32 characters | PASS |
| Multi-byte Unicode / emojis in label | Preserved and truncated to 32 | Preserved, length <= 32 | PASS |
| Zero buttons configured (`[]` or `None`) | `"buttons"` key omitted from `rpc.update` | `"buttons"` key completely omitted | PASS |
| Rapid configuration queue flooding | Coalesced under lock without crash | Processed safely | PASS |

---

## 5. Caveats

- **Discord Self-Preview Behavior**: The Discord desktop client disables rich presence buttons when a user views their own profile. All other Discord users viewing the profile see active, interactive, clickable buttons that navigate to the designated URLs.
- **URL Schema vs Network Validity**: `sanitize_buttons()` validates string structure, length, and HTTPS protocol prefixing; it does not perform asynchronous DNS resolution or HTTP head checks, which would block the presence update pipeline.

---

## 6. Conclusion

Milestone M8 (Requirement R2: Discord Interactive Profile Buttons) is **APPROVED**:
- `sanitize_buttons()` correctly enforces all validation rules, length caps, and HTTPS upgrades.
- Empty list arrays (`[]`) are never dispatched to `pypresence`.
- Web UI in `#view-config` provides interactive configuration, glass styling, custom scrollbars, and persistent storage in `config.json`.
- 100% of master E2E tests (149/149) pass.
- Application bundle is synchronized and verified.

---

## 7. Verification Method

To independently verify this evaluation, run:

1. **Master Test Suite**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   ```
   *Expected*: 149 passed / 149 total across Tiers 1–5, 0 failures, exit code 0.

2. **Milestone 8 Unit Suite**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_milestone8_buttons.py
   ```
   *Expected*: 27 passed, 0 failures, exit code 0.

3. **Challenger Adversarial Stress Suites**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_challenger_m8_buttons.py tests/test_challenger_m8_stress.py
   ```
   *Expected*: 31 passed, 0 failures, exit code 0.

4. **Bundle Synchronization**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python sync_bundle.py
   ```
   *Expected*: Reports clean synchronization and verification of `/Applications/League of Legends RPC.app`.
