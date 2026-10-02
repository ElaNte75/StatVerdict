# Extra guide sources: research (2026-10-02)

Checked from the build container (plain page requests, browser-like agent). Goal: a second/third source for the
Guide drawer, copied 1:1 and verified, never mixed with another source.

| Site | Reachable | robots.txt | What the pages hold (Guardian Druid checked) | Verdict |
|---|---|---|---|---|
| Method (method.gg) | yes | allows everything except /admin, /board | Written guide per spec (Midnight 12.1, updated 3 Sep 2026): stat priority line ("Item Level > Haste > Vers >= Crit > Mastery"), Best in Slot per slot with source, split Overall / Raiding / Mythic+, enchants, gems, trinkets, embellishments. **No stat targets.** | Best first candidate: a named "camp", clean structure. Targets to be derived from the listed gear (our own arithmetic, labelled so). Terms forbid copying/republishing their text: copy facts only (item names, stat order), no prose. |
| Murlok (murlok.io) | yes | allows everything | Built from the top 50 players per spec (Battle.net data, refreshed every 8 h): **optimal secondary ratings with percentages (29% crit +871 ...), stat priority**, BiS gear, trinkets, enchants, gems, talents, per content (M+, raid, PvP). | Closest match to the current data shape (targets included). Second candidate. Players' data, not an editorial guide. |
| Wowhead | yes | explicitly blocks AI crawlers (ClaudeBot, anthropic-ai, Scrapy ...) | Full guides | Skip: their stated policy is against automated AI access. |
| Icy Veins, u.gg, Archon, Warcraft Logs | 403 to plain requests here | - | - | Icy Veins/u.gg already used through ClassCodex. |
| WoWMeta | yes | no rules | not checked | later |
| Bloodmallet | yes | - | simulation results, not a guide | not a guide source |

Plan: add one source at a time; import, verify against the live pages from several sides, then the next.

## Method import, state (2026-10-02)
- `tools/method_guides.py` reads the six tank guides (priority per hero tree, Best in Slot tabs Raid / Mythic+, enchants,
  gems) into `tools/data/method/<slug>.json` (facts only).
- `tools/method_targets.py` adds up the listed set (item level 334 = season top, one unique Diamond, secondary gem only into
  real sockets, enchants only on slots that take them) into `tools/data/method/<slug>-targets.json`.
- Gaps: Brewmaster and Protection Warrior pages describe enchants/gems in prose, so the ring enchant is not read
  (`incomplete` is set); head enchants are leech/avoidance (no secondary rating). Where a guide says "A or B" the first is used.
- Not in the addon yet.
