# Dispatch Assignment — explorer_survey_3

## Objective
Investigate Riot Data Dragon API, Champion name normalization, rank assets, and Discord RPC (`pypresence`) concurrency and thread safety architecture.

## Context & Inputs
- Original Request: `/Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md`
- Working Directory: `/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3`
- Project Root: `/Users/victormanuel/discord-rpc`

## Scope
1. Champion name normalization for Data Dragon:
   - Identify edge cases (Wukong -> MonkeyKing, Cho'Gath -> Chogath, Kai'Sa -> Kaisa, Vel'Koz -> Velkoz, Kha'Zix -> Khazix, Bel'Veth -> Belveth, K'Sante -> KSante, LeBlanc -> Leblanc, Nunu & Willump -> Nunu, Renata Glasc -> Renata, etc.).
   - Data Dragon CDN URLs for champion square icons (e.g. `https://ddragon.leagueoflegends.com/cdn/<version>/img/champion/<id>.png`), determine latest DDragon version fetching or fallback.
2. Rank representation & Discord Rich Presence asset keys:
   - Ranks from Iron to Challenger. Division rules (Apex tiers Master, Grandmaster, Challenger have NO divisions, avoid "Challenger II").
3. Concurrency & Threading:
   - PyObjC runs on the main thread (AppKit runloop). Long-running network calls or Discord RPC socket communication in `pypresence` must NOT run on the main thread.
   - Design thread-safe bridge (`threading.Lock`, worker thread or queue) between UI actions and `pypresence.Presence` calls.
   - Auto-reconnect resilience on Discord restart, error handling for pipe disconnects without crashing.
   - Auto-restart timer (resetting elapsed time every 20-30 min) implementation.

## Deliverable
Write a comprehensive report to `/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3/handoff.md`.
Report back via `send_message` to parent orchestrator when complete.

## 2026-09-27T08:34:02Z
<USER_REQUEST>
You are explorer_survey_3 (LoL Data Dragon & Concurrency Explorer) for the Discord RPC redesign project.
Your assigned working directory is:
/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3

MANDATORY INPUTS:
- Original Request: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md
- Dispatch Instructions: /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3/DISPATCH.md
- Project Root: /Users/victormanuel/discord-rpc

Task:
Read ORIGINAL_REQUEST.md and DISPATCH.md. Research Riot Data Dragon API (versions, champion normalization rules, asset URLs, ranks Iron to Challenger without invalid division numbers), and Discord RPC (pypresence) concurrency safety (threading.Lock, main thread AppKit isolation, reconnect loops, auto-restart timer). Produce a detailed technical specification and architecture in:
/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3/handoff.md.

Update your progress.md regularly with timestamps. Send a message to the orchestrator when your handoff.md is ready.
</USER_REQUEST>
