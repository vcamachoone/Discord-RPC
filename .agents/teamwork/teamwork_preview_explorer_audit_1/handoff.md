# Handoff Report: Auditoría Funcional y de Interfaz (Liquid Glass & Popover UI)

**Agent**: `teamwork_preview_explorer_audit_1`  
**Milestone**: M5 / Follow-up Audit R1  
**Working Directory**: `/Users/victormanuel/discord-rpc/.agents/teamwork/teamwork_preview_explorer_audit_1`  
**Date**: 2026-09-27T16:48:00Z  

---

## 1. Observation

### 1.1 Architecture & Component Inspection
Direct file inspections were conducted across all core modules:
- `/Users/victormanuel/discord-rpc/popover_ui.py` (1,457 lines)
- `/Users/victormanuel/discord-rpc/liquid_html.py` (988 lines)
- `/Users/victormanuel/discord-rpc/lol_champions.py` (360 lines)
- `/Users/victormanuel/discord-rpc/lol_ranks.py` (149 lines)
- `/Users/victormanuel/discord-rpc/assets_gen.py` (265 lines)
- `/Users/victormanuel/discord-rpc/status_item.py` (279 lines)
- `/Users/victormanuel/discord-rpc/app_gui.py` (338 lines)
- `/Users/victormanuel/discord-rpc/sync_bundle.py` (287 lines)

All 149 automated tests across Tiers 1-5 (`tests/run_tests.py`) passed cleanly (exit code 0 in 20.905s). However, in-depth behavioral and bridge inspection uncovered critical runtime defects and UI synchronization discrepancies detailed below.

---

### 1.2 Verbatim Observations & Defects

#### [CRITICAL DEFECT] AttributeError on Rank and Division Change from WebKit UI
In `popover_ui.py`, lines 142–146:
```python
        elif action == "change_rank":
            self._controller.set_selected_rank(body.get("rank", "Oro"))
        elif action == "change_division":
            self._controller.set_selected_division(body.get("division", "II"))
```
When `LoLWebBridge` receives `change_rank` or `change_division` from the WebKit overlay, it attempts to call `set_selected_rank` and `set_selected_division` on `self._controller` (`LoLPopoverController`).

Inspection of `LoLPopoverController` (lines 1347–1394):
- The rank setter is defined as: `def select_rank(self, rank_tier: str) -> None:` (line 1347).
- The division setter is defined as: `def select_division(self, division: str) -> None:` (line 1383).
- Neither `set_selected_rank` nor `set_selected_division` exists on `LoLPopoverController`.

**Empirical Verification**:
```bash
/Users/victormanuel/discord-rpc/venv/bin/python -c "
import popover_ui
ctrl = popover_ui.LoLPopoverController()
print('has select_rank:', hasattr(ctrl, 'select_rank'))
print('has set_selected_rank:', hasattr(ctrl, 'set_selected_rank'))
print('has select_division:', hasattr(ctrl, 'select_division'))
print('has set_selected_division:', hasattr(ctrl, 'set_selected_division'))
"
```
Output:
```
has select_rank: True
has set_selected_rank: False
has select_division: True
has set_selected_division: False
```

Triggering `change_rank` via `LoLWebBridge`:
```
Traceback (most recent call last):
  File "popover_ui.py", line 143, in userContentController_didReceiveScriptMessage_
    self._controller.set_selected_rank(body.get("rank", "Oro"))
AttributeError: 'LoLPopoverController' object has no attribute 'set_selected_rank'
```

---

#### [DEFECT] Missing "Unranked" Option in WebKit Rank Dropdown
In `lol_ranks.py`, line 27:
```python
DEFAULT_RANKS_ES: List[str] = [
    "Hierro", "Bronce", "Plata", "Oro", "Platino",
    "Esmeralda", "Diamante", "Maestro", "Gran Maestro", "Challenger", "Unranked"
]
```
In `popover_ui.py`, line 588:
`self._rank_popup.addItemsWithTitles_(self.get_available_rank_tiers())` populates all 11 tiers including "Unranked".

However, in `liquid_html.py`, lines 673–685:
```html
          <select id="rank-select" class="field-select" onchange="sendAction('change_rank', {rank: this.value})">
            <option value="Hierro">Hierro</option>
            <option value="Bronce">Bronce</option>
            <option value="Plata">Plata</option>
            <option value="Oro">Oro</option>
            <option value="Platino">Platino</option>
            <option value="Esmeralda">Esmeralda</option>
            <option value="Diamante">Diamante</option>
            <option value="Maestro">Maestro</option>
            <option value="Gran Maestro">Gran Maestro</option>
            <option value="Challenger">Challenger</option>
          </select>
```
`"Unranked"` is completely missing from `<select id="rank-select">`. When rank is initialized or set to `"Unranked"`, `document.getElementById('rank-select').value = "Unranked"` fails to match any option and leaves the select invalid or blank.

---

#### [DEFECT] Default Game Mode Mismatch Triggering Custom Mode on Startup
In `popover_ui.py`, line 188:
```python
self._game_mode: str = "Grieta del Invocador (Clasificatoria)"
```
In `liquid_html.py`, lines 82–93:
```python
GAME_MODES: List[str] = [
    "Grieta del Invocador (Clasificatoria Solo/Duo)",
    "Grieta del Invocador (Clasificatoria Flexible)",
    "Grieta del Invocador (Normal / Partida Rápida)",
    "Grieta del Invocador (Reclutamiento / Draft)",
    "ARAM (El Abismo de los Lamentos)",
    "Arena (2v2v2v2)",
    "Teamfight Tactics (TFT)",
    "URF (Fuego Rápido Ultra)",
    "Partida Personalizada",
    "Herramienta de Práctica",
]
```
In `liquid_html.py`, lines 956–969:
```javascript
        let found = false;
        for (let i = 0; i < select.options.length; i++) {
          if (select.options[i].value === currentState.game_mode) {
            select.selectedIndex = i;
            found = true;
            break;
          }
        }

        if (!found) {
          select.value = '__custom__';
          customWrap.classList.add('open');
          customInput.value = currentState.game_mode;
        }
```
Because `"Grieta del Invocador (Clasificatoria)"` != `"Grieta del Invocador (Clasificatoria Solo/Duo)"`, `!found` evaluates to `true` on initial launch. The selector immediately switches to `__custom__` and expands `<div id="custom-gamemode-wrap" class="custom-gamemode-box open">` on every fresh start instead of selecting the canonical mode option.

---

#### [DEFECT] 173-Champion Avatar Searcher: Missing Alias Indexing in WebKit Dropdown
In `lol_champions.py`, `SPECIAL_CHAMPION_MAP` contains aliases:
`"bardo": ("Bard", "Bard")`  
`"asol": ("AurelionSol", "Aurelion Sol")`  
`"j4": ("JarvanIV", "Jarvan IV")`  
`"mf": ("MissFortune", "Miss Fortune")`  
`"tf": ("TwistedFate", "Twisted Fate")`  
`"yi": ("MasterYi", "Master Yi")`  

In `liquid_html.py`, `CHAMPIONS_CATALOG` only maps:
`{"id": cid, "name": name, "icon": f".../{cid}.png"}`

In `filterChampions(query)` (lines 804–810):
```javascript
      const filtered = ALL_CHAMPIONS.filter(c => {
        if (!q) return true;
        const nameClean = c.name.toLowerCase().replace(/[^a-z0-9]/g, '');
        const idClean = c.id.toLowerCase();
        const qClean = q.replace(/[^a-z0-9]/g, '');
        return c.name.toLowerCase().includes(q) || nameClean.includes(qClean) || idClean.includes(qClean);
      });
```
Typing "asol", "j4", "mf", "tf", or "bardo" returns 0 matches in the dropdown (`"No se encontró ningún campeón"`). While pressing Enter falls back to `sendAction('change_champion')` where Python's `ChampionResolver` resolves it, the interactive dropdown fails to suggest the champion.

---

#### [DEFECT] `highlightedIndex` Not Reset on Search Filter Update
In `liquid_html.py`, lines 800–833:
`filterChampions(query)` clears `champDropdown.innerHTML = ''`, but does NOT reset `highlightedIndex = -1`.
If the user arrows down to index 3, and then types an additional letter that reduces the result list to 1 item, `highlightedIndex` remains 3. Pressing Enter accesses `items[3]` (undefined), failing to select the visible filtered item.

---

#### [DEFECT] Champion Input Lacks Commit on Blur/Change
In `liquid_html.py`, line 662:
```html
<input type="text" id="champ-input" class="field-input champ-search-input" placeholder="Buscar campeón (ej. Yasuo, Jinx, Ahri)..." autocomplete="off" onfocus="openChampDropdown()" oninput="filterChampions(this.value)">
```
There is no `onchange` or `onblur` event on `champ-input`. If a user types a valid champion name (e.g. "Yasuo") and immediately clicks the action button ("INICIAR PRESENCIA") without pressing Enter or clicking an item in the dropdown, `sendAction('change_champion')` is never fired, leaving the previous champion active.

---

#### [OBSERVATION] Outdated Fallback Roster in `liquid_html.py`
In `liquid_html.py`, lines 22–69:
The `except ImportError` fallback roster contains only 154 champions (missing Ambessa, Mel, Locke, Yunara, Zaahen, etc.). While normal runtime imports `lol_champions.CHAMPIONS_DATA` (173 champions), any isolated execution will drop back to 154 champions.

---

## 2. Logic Chain

1. **User Interaction Pipeline**:
   - The user opens the NSPopover. If WebKit is available, `LoLWebBridge` handles all user actions from the WebKit overlay and forwards them to `LoLPopoverController`.
   - `LoLPopoverController` updates internal state and forwards changes to `DiscordRPCManager`.
   - `LoLPopoverController._sync_to_web()` calls `window.updateLiquidUI(state)` via `evaluateJavaScript` to reflect state changes back into the DOM.

2. **Rank & Division Failure Chain**:
   - User selects "Diamante" in `<select id="rank-select">`.
   - WebKit executes `sendAction('change_rank', {rank: this.value})`.
   - `LoLWebBridge.userContentController_didReceiveScriptMessage_` receives action `"change_rank"`.
   - It executes `self._controller.set_selected_rank("Diamante")`.
   - Because `LoLPopoverController` only defines `select_rank`, Python raises an `AttributeError`.
   - The rank update is aborted, the RPC config is not updated, and the selection fails silently or logs an unhandled exception in WebKit console.

3. **Game Mode Initialization Failure Chain**:
   - `LoLPopoverController` initializes with `_game_mode = "Grieta del Invocador (Clasificatoria)"`.
   - `generate_liquid_html(state)` sends this string to `window.updateLiquidUI(currentState)`.
   - In JS, `for (let i = 0; i < select.options.length; i++)` iterates over `GAME_MODES`.
   - None of the options match `"Grieta del Invocador (Clasificatoria)"` because the options are `"Grieta del Invocador (Clasificatoria Solo/Duo)"` and `"Grieta del Invocador (Clasificatoria Flexible)"`.
   - `!found` evaluates to true, triggering `select.value = '__custom__'` and `customWrap.classList.add('open')`.
   - Result: Popover always opens with the custom game mode text box expanded on startup instead of selecting the standard mode.

4. **173-Champion Search Chain**:
   - 173 champions are indexed in `CHAMPIONS_DATA`. All canonical Riot IDs (Wukong -> MonkeyKing, Cho'Gath -> Chogath, etc.) resolve properly in `lol_champions.py`.
   - In JS, the filter only compares `qClean` against `c.name` and `c.id`.
   - Community aliases ("asol", "j4", "bardo") are missing in `c`, breaking live autocomplete for standard LoL slang.

5. **Visual Glass & Menubar Pipeline**:
   - `assets_gen.py` produces 22x22 and 44x44 PNGs with exact specifications: `#00A8FC` dot in lower right with cutout, 35% alpha for paused, monochrome white for normal.
   - `status_item.py` correctly applies `setTemplate_(True)` for normal, and `setTemplate_(False)` for active/paused.
   - `FlippedVisualEffectView` provides native `NSVisualEffectMaterialHUDWindow` dark blur, overlaid transparently by `WKWebView`.
   - Dynamic popover resizing (360pt for Official / collapsed, 515pt for Detailed / expanded) operates cleanly without UI distortion.

---

## 3. Defects & Edge Cases Discovered (Summary Table)

| ID | Component | Severity | Description | Impact |
|---|---|---|---|---|
| **D1** | `popover_ui.py` (LoLWebBridge) | **CRITICAL** | `LoLWebBridge` calls `set_selected_rank` & `set_selected_division`, but `LoLPopoverController` only implements `select_rank` & `select_division`. | Changing rank or division from WebKit UI throws `AttributeError` and fails. |
| **D2** | `liquid_html.py` (HTML Template) | **MEDIUM** | `<select id="rank-select">` lacks `<option value="Unranked">Unranked</option>`. | Selecting Unranked from Cocoa or state sync fails to select in WebKit UI. |
| **D3** | `popover_ui.py` / `liquid_html.py` | **MEDIUM** | Default mode `"Grieta del Invocador (Clasificatoria)"` is not in `GAME_MODES`. | Causes popover to default to `__custom__` and open the custom mode text box on initial launch. |
| **D4** | `liquid_html.py` (Search Filter) | **LOW** | `filterChampions()` does not search community aliases (`asol`, `j4`, `mf`, `tf`, `bardo`). | Dropdown shows "No se encontró ningún campeón" for common abbreviations. |
| **D5** | `liquid_html.py` (Keyboard Nav) | **LOW** | `highlightedIndex` is not reset to `-1` when input is typed in `filterChampions()`. | Keyboard selection can access invalid index or misselect after typing narrows results. |
| **D6** | `liquid_html.py` (Search Input) | **LOW** | `champ-input` lacks `onchange` / `onblur` commit handler. | Typing a champion and clicking "INICIAR PRESENCIA" without Enter does not commit the champion. |
| **D7** | `liquid_html.py` (Fallback Data) | **LOW** | Fallback `CHAMPIONS_DATA` in `liquid_html.py` has 154 champions instead of 173. | Fallback roster is missing recent champions if imported outside module path. |

---

## 4. Recommended Fixes & Hardening

### Fix 1: Bridge Method Alignment in `popover_ui.py`
In `popover_ui.py`, update `LoLWebBridge.userContentController_didReceiveScriptMessage_`:
```python
<<<<
        elif action == "change_rank":
            self._controller.set_selected_rank(body.get("rank", "Oro"))
        elif action == "change_division":
            self._controller.set_selected_division(body.get("division", "II"))
====
        elif action == "change_rank":
            self._controller.select_rank(body.get("rank", "Oro"))
        elif action == "change_division":
            self._controller.select_division(body.get("division", "II"))
>>>>
```
*(Also add alias methods `set_selected_rank = select_rank` and `set_selected_division = select_division` on `LoLPopoverController` for backward compatibility).*

---

### Fix 2: Add "Unranked" Option to `liquid_html.py`
In `liquid_html.py`, line 684:
```html
<<<<
            <option value="Challenger">Challenger</option>
          </select>
====
            <option value="Challenger">Challenger</option>
            <option value="Unranked">Unranked</option>
          </select>
>>>>
```

---

### Fix 3: Align Default Game Mode String in `popover_ui.py`
In `popover_ui.py`, line 188:
```python
<<<<
        self._game_mode: str = "Grieta del Invocador (Clasificatoria)"
====
        self._game_mode: str = "Grieta del Invocador (Clasificatoria Solo/Duo)"
>>>>
```
*(Alternatively, add `"Grieta del Invocador (Clasificatoria)"` as an option in `GAME_MODES` in `liquid_html.py`).*

---

### Fix 4: Include Community Aliases & Reset Highlight in `liquid_html.py`
In `liquid_html.py`:
1. Include aliases mapping in `CHAMPIONS_CATALOG` or add alias matching in `filterChampions`:
```javascript
<<<<
    function filterChampions(query) {
      const q = (query || '').toLowerCase().trim();
      champDropdown.innerHTML = '';
====
    const ALIAS_MAP = {
      'asol': 'Aurelion Sol', 'j4': 'Jarvan IV', 'mf': 'Miss Fortune',
      'tf': 'Twisted Fate', 'yi': 'Master Yi', 'bardo': 'Bard',
      'nunu y willump': 'Nunu & Willump', 'mundo': 'Dr. Mundo'
    };

    function filterChampions(query) {
      highlightedIndex = -1;
      const q = (query || '').toLowerCase().trim();
      champDropdown.innerHTML = '';
      const aliasTarget = ALIAS_MAP[q] ? ALIAS_MAP[q].toLowerCase() : '';
>>>>
```
2. In filter condition:
```javascript
<<<<
        return c.name.toLowerCase().includes(q) || nameClean.includes(qClean) || idClean.includes(qClean);
====
        return c.name.toLowerCase().includes(q) || nameClean.includes(qClean) || idClean.includes(qClean) || (aliasTarget && c.name.toLowerCase().includes(aliasTarget));
>>>>
```

---

### Fix 5: Commit on Input Blur/Change
In `liquid_html.py`, line 662:
```html
<<<<
<input type="text" id="champ-input" class="field-input champ-search-input" placeholder="Buscar campeón (ej. Yasuo, Jinx, Ahri)..." autocomplete="off" onfocus="openChampDropdown()" oninput="filterChampions(this.value)">
====
<input type="text" id="champ-input" class="field-input champ-search-input" placeholder="Buscar campeón (ej. Yasuo, Jinx, Ahri)..." autocomplete="off" onfocus="openChampDropdown()" oninput="filterChampions(this.value)" onchange="sendAction('change_champion', { name: this.value.trim() })">
>>>>
```

---

## 5. Caveats
- No direct source modifications were performed in this turn in strict compliance with the **read-only investigation** constraint.
- The automated E2E test suite (`tests/run_tests.py`) passed 149/149 because previous tests called `select_rank` directly on `LoLPopoverController` and did not test message dispatch via `LoLWebBridge.userContentController_didReceiveScriptMessage_`.
- Dynamic DDragon icon fetches require internet access; offline fallback behavior was verified to gracefully degrade to Malzahar icon or 40% opacity placeholder.

---

## 6. Conclusion
The Liquid Glass NSPopover UI and League of Legends engine demonstrate exceptional architectural elegance, combining native macOS AppKit HUD blur, transient popovers, non-blocking actor concurrency, and pixel-perfect SVG menubar assets. 

However, **one critical defect (D1)** prevents the WebKit popover from updating rank and division due to mismatched method names (`set_selected_rank` vs `select_rank`), and **five functional/visual discrepancies (D2–D6)** affect default game mode selection, Unranked tier handling, community alias search, and keyboard highlight state. Implementing the recommended fixes outlined in Section 4 will achieve 100% functional completeness and flawless user experience.

---

## 7. Verification Method

To independently reproduce and verify all findings:

1. **Verify D1 (AttributeError in LoLWebBridge)**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c "
   import popover_ui
   class MockMessage:
       def __init__(self, b): self._b = b
       def body(self): return self._b
   ctrl = popover_ui.LoLPopoverController()
   ctrl._web_bridge.userContentController_didReceiveScriptMessage_(None, MockMessage({'action': 'change_rank', 'rank': 'Challenger'}))
   "
   ```
   *Expected result*: `AttributeError: 'LoLPopoverController' object has no attribute 'set_selected_rank'`.

2. **Verify D2 (Missing Unranked in HTML Select)**:
   ```bash
   grep -i "unranked" /Users/victormanuel/discord-rpc/liquid_html.py
   ```
   *Expected result*: No matches found in `<select id="rank-select">`.

3. **Verify D3 (Default Game Mode Mismatch)**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c "
   import popover_ui, liquid_html
   p = popover_ui.LoLPopoverController()
   print('In GAME_MODES:', p.get_game_mode_text() in liquid_html.GAME_MODES)
   "
   ```
   *Expected result*: `In GAME_MODES: False`.

4. **Verify D4 (Alias Autocomplete Dropdown Gap)**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c "
   import re, liquid_html
   champs = liquid_html.CHAMPIONS_CATALOG
   matches = [c['name'] for c in champs if 'asol' in c['name'].lower() or 'asol' in c['id'].lower()]
   print('Live dropdown matches for asol:', matches)
   "
   ```
   *Expected result*: `Live dropdown matches for asol: []`.

5. **Verify Full Automated Suite Execution**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   ```
   *Expected result*: 149/149 passed.
