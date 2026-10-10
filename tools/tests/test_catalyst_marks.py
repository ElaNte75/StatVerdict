"""The gold "!" on a worn piece of the character sheet when the Catalyst would make it Best in Slot."""
from __future__ import annotations

import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class CatalystMarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        lua = self.lua
        lua.execute("""
        local function Frame()
            local f = { shown = true, marks = {} }
            function f:RegisterEvent() end
            function f:SetScript() end
            function f:HookScript() end
            function f:IsShown() return self.shown end
            function f:GetID() return self.id end
            function f:GetWidth() return 40 end
            function f:GetHeight() return 40 end
            function f:GetEffectiveAlpha() return 1 end
            function f:GetObjectType() return "Button" end
            function f:CreateFontString()
                local fs = { shown = false }
                function fs:SetDrawLayer(layer, sub) if (sub or 0) > 7 or (sub or 0) < -8 then error("draw sublevel out of range") end end
                function fs:SetFont(file, size) self.size = size end
                function fs:SetText(t) self.text = t end
                function fs:SetPoint() end
                function fs:SetShown(v) self.shown = v end
                function fs:Show() self.shown = true end
                function fs:Hide() self.shown = false end
                return fs
            end
            function f:CreateTexture()
                local tx = { shown = false, points = {} }
                function tx:SetDrawLayer(layer, sub) if (sub or 0) > 7 or (sub or 0) < -8 then error("draw sublevel out of range") end end
                function tx:SetTexture(p) self.path = p end
                function tx:SetSize(w, h) self.w, self.h = w, h end
                function tx:ClearAllPoints() self.points = {} end
                function tx:SetPoint(...) self.points[#self.points + 1] = { ... } end
                function tx:Show() self.shown = true end
                function tx:Hide() self.shown = false end
                return tx
            end
            return f
        end
        CreateFrame = function() return Frame() end
        C_Timer = { After = function() end }
        NUM_CONTAINER_SCAN_FRAMES = 0
        CharacterLegsSlot = Frame(); CharacterLegsSlot.id = 7
        CharacterHeadSlot = Frame(); CharacterHeadSlot.id = 1
        WORN = { [7] = "item:111", [1] = "item:222" }
        GetInventoryItemLink = function(unit, slot) return WORN[slot] end
        """)
        load_addon_file(lua, self.ns, "UI/SV_UpgradeIndicatorView.lua")
        self.ns.GetTooltipEvaluationContexts = lambda: lua.table(profile=lua.table(goal="RAID"))
        # What ns.GetWornPieceInfo says about each worn piece (the rules themselves are tested in test_worn_info).
        self.ns.GetWornPieceInfo = lua.eval("""
        function(link)
            if link == 'item:111' then return { gain = 96.3 } end
            if link == 'item:222' then return { bis = true } end
            if link == 'item:333' then return { shared = true, otherLabel = 'Off Spec' } end
            if link == 'item:444' then return { bis = true, shared = true, otherLabel = 'Off Spec' } end
        end""")

    def mark_shown(self, frame: str, field: str = "StatVerdictCatalystMark") -> bool:
        return bool(self.lua.eval(f"{frame}.{field} and {frame}.{field}.shown or false"))

    def test_only_the_piece_the_catalyst_improves_is_marked(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterLegsSlot"))
        self.assertFalse(self.mark_shown("CharacterHeadSlot"))

    def test_a_best_in_slot_piece_gets_the_gold_tag_not_the_exclamation(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterHeadSlot", "StatVerdictBisMark"))
        self.assertFalse(self.mark_shown("CharacterLegsSlot", "StatVerdictBisMark"))

    def test_the_option_switches_every_mark_off(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.lua.execute("StatVerdictDB = { showCharacterMarks = false }")
        self.ns.RefreshCatalystMarks()
        self.assertFalse(self.mark_shown("CharacterLegsSlot"))
        self.assertFalse(self.mark_shown("CharacterHeadSlot", "StatVerdictBisMark"))
        self.lua.execute("StatVerdictDB = {}")  # never set: on
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterLegsSlot"))

    def shared_mark(self, frame):
        mark = self.lua.eval(f"{frame}.StatVerdictSharedMark")
        if not mark or not bool(mark.shown):
            return None
        return float(mark.w), str(mark.points[1][3])  # size and the corner of the icon it hangs on

    def letters_size(self, frame, field):
        return float(self.lua.eval(f"{frame}.{field}.size"))

    def test_a_piece_only_in_both_sets_gets_the_empty_ring(self) -> None:
        self.lua.execute("WORN[7] = 'item:333'")
        self.ns.RefreshCatalystMarks()
        self.assertEqual((31.0, "CENTER"), self.shared_mark("CharacterLegsSlot"))
        self.assertTrue(str(self.lua.eval("CharacterLegsSlot.StatVerdictSharedMark.path")).endswith("SharedRing2"))
        self.assertFalse(self.mark_shown("CharacterLegsSlot"))  # no CAT inside
        self.assertFalse(self.mark_shown("CharacterLegsSlot", "StatVerdictBisMark"))  # no BIS inside

    def test_bis_in_both_sets_is_the_letters_inside_the_ring(self) -> None:
        self.lua.execute("WORN[1] = 'item:444'")
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterHeadSlot", "StatVerdictBisMark"))
        self.assertEqual((31.0, "CENTER"), self.shared_mark("CharacterHeadSlot"))
        self.assertEqual(10.0, self.letters_size("CharacterHeadSlot", "StatVerdictBisMark"))  # small enough for the ring

    def test_bis_alone_is_the_bigger_letters_without_a_ring(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterHeadSlot", "StatVerdictBisMark"))
        self.assertIsNone(self.shared_mark("CharacterHeadSlot"))
        self.assertEqual(12.0, self.letters_size("CharacterHeadSlot", "StatVerdictBisMark"))

    def test_cat_in_both_sets_is_cat_inside_the_ring(self) -> None:
        self.lua.execute("WORN[7] = 'item:555'")
        self.ns.GetWornPieceInfo = self.lua.eval(
            "function(link) if link == 'item:555' then return { gain = 10, shared = true, otherLabel = 'Off Spec' } end end")
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterLegsSlot"))  # CAT
        self.assertEqual((31.0, "CENTER"), self.shared_mark("CharacterLegsSlot"))
        self.assertEqual(10.0, self.letters_size("CharacterLegsSlot", "StatVerdictCatalystMark"))

    def test_the_ring_goes_when_the_piece_is_no_longer_in_both_sets(self) -> None:
        self.lua.execute("WORN[1] = 'item:444'")
        self.ns.RefreshCatalystMarks()
        self.lua.execute("WORN[1] = 'item:222'")  # BIS, in one set only
        self.ns.RefreshCatalystMarks()
        self.assertIsNone(self.shared_mark("CharacterHeadSlot"))
        self.assertEqual(12.0, self.letters_size("CharacterHeadSlot", "StatVerdictBisMark"))

    def test_one_piece_that_fails_does_not_stop_the_marks_of_the_others(self) -> None:
        self.ns.GetWornPieceInfo = self.lua.eval(
            "function(link) if link == 'item:111' then error('boom') end if link == 'item:222' then return { bis = true } end end")
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterHeadSlot", "StatVerdictBisMark"))  # the head comes before the legs

    def test_a_piece_in_one_set_has_no_arrows(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.assertIsNone(self.shared_mark("CharacterLegsSlot"))
        self.assertIsNone(self.shared_mark("CharacterHeadSlot"))

    def test_the_arrows_go_with_the_option_off(self) -> None:
        self.lua.execute("WORN[7] = 'item:333'")
        self.ns.RefreshCatalystMarks()
        self.lua.execute("StatVerdictDB = { showCharacterMarks = false }")
        self.ns.RefreshCatalystMarks()
        self.assertIsNone(self.shared_mark("CharacterLegsSlot"))

    def test_the_mark_goes_when_the_piece_is_changed(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.lua.execute("WORN[7] = 'item:333'")
        self.ns.RefreshCatalystMarks()
        self.assertFalse(self.mark_shown("CharacterLegsSlot"))


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class BagLetterTests(unittest.TestCase):
    """MS and OS marks on a bag item: independent, both shown when the piece is in both loadouts."""

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        lua = self.lua
        lua.execute("""
        local function Frame()
            local f = { shown = true }
            function f:RegisterEvent() end
            function f:SetScript() end
            function f:HookScript() end
            function f:IsShown() return self.shown end
            function f:GetWidth() return 40 end
            function f:GetHeight() return 40 end
            function f:GetEffectiveAlpha() return 1 end
            function f:GetObjectType() return "Button" end
            function f:CreateFontString()
                local fs = { shown = false, points = {} }
                function fs:SetDrawLayer() end
                function fs:SetFont() end
                function fs:SetText(t) self.text = t end
                function fs:ClearAllPoints() self.points = {} end
                function fs:SetPoint(...) self.points[#self.points + 1] = { ... } end
                function fs:GetFont() return "font", 13, "OUTLINE" end
                function fs:Show() self.shown = true end
                function fs:Hide() self.shown = false end
                function fs:SetShown(v) self.shown = v end
                return fs
            end
            function f:CreateTexture()
                local tx = { shown = false, points = {} }
                function tx:SetSize(w, h) self.w, self.h = w, h end
                function tx:SetTexture(p) self.path = p end
                function tx:SetDrawLayer(layer, sub) if (sub or 0) > 7 or (sub or 0) < -8 then error("draw sublevel out of range") end end
                function tx:SetVertexColor() end
                function tx:SetPoint(...) self.points[#self.points + 1] = { ... } end
                function tx:ClearAllPoints() self.points = {} end
                function tx:Show() self.shown = true end
                function tx:Hide() self.shown = false end
                return tx
            end
            return f
        end
        CreateFrame = function() return Frame() end
        C_Timer = { After = function() end }
        NUM_CONTAINER_SCAN_FRAMES = 0
        BAG_BUTTON = Frame()
        """)
        load_addon_file(lua, self.ns, "UI/SV_UpgradeIndicatorView.lua")

    def show(self, role: str):
        self.ns.GetUpgradeIndicatorItemState = self.lua.eval(
            "function() return { kind = '%s', specRole = '%s' } end" % (role, role))
        self.ns.UpdateUpgradeIndicatorFrame(self.lua.eval("BAG_BUTTON"), "item:1", self.lua.eval("{ source = 'bags' }"))

    def letters(self):
        main = self.lua.eval("BAG_BUTTON.StatVerdictSpecValueIndicator and BAG_BUTTON.StatVerdictSpecValueIndicator.shown or false")
        off = self.lua.eval("BAG_BUTTON.StatVerdictOffSpecIndicator and BAG_BUTTON.StatVerdictOffSpecIndicator.shown or false")
        return bool(main), bool(off)

    def test_each_role_shows_its_own_mark(self) -> None:
        self.show("main_spec")
        self.assertEqual((True, False), self.letters())
        self.show("off_spec")
        self.assertEqual((False, True), self.letters())

    def ring_shown(self) -> bool:
        return bool(self.lua.eval("BAG_BUTTON.StatVerdictBagRing and BAG_BUTTON.StatVerdictBagRing.shown or false"))

    def test_a_piece_in_both_loadouts_shows_the_gold_ring_not_letters(self) -> None:
        self.show("both_specs")
        self.assertEqual((False, False), self.letters())  # no MS, no OS, no M/O
        self.assertTrue(self.ring_shown())
        self.assertTrue(str(self.lua.eval("BAG_BUTTON.StatVerdictBagRing.path")).endswith("SharedRingBold"))  # the bolder drawing
        self.assertEqual("TOPRIGHT", str(self.lua.eval("BAG_BUTTON.StatVerdictBagRing.points[1][3]")))  # where the letters were

    def test_the_ring_is_not_shown_for_a_piece_in_one_loadout(self) -> None:
        self.show("both_specs")
        self.show("main_spec")
        self.assertFalse(self.ring_shown())
        self.assertEqual((True, False), self.letters())

    def test_ms_and_os_sit_at_the_top_right(self) -> None:
        for role, field in (("main_spec", "StatVerdictSpecValueIndicator"), ("off_spec", "StatVerdictOffSpecIndicator")):
            self.show(role)
            self.assertEqual("TOPRIGHT", str(self.lua.eval(f"BAG_BUTTON.{field}.points[1][3]")), role)

    def test_marks_go_when_the_piece_leaves_both(self) -> None:
        self.show("both_specs")
        self.show("main_spec")
        self.assertEqual((True, False), self.letters())
        self.assertIn("MS", str(self.lua.eval("BAG_BUTTON.StatVerdictSpecValueIndicator.text")))
        self.assertFalse(self.ring_shown())


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class CatalystMarkCostTests(unittest.TestCase):
    """Measured in the game: one redraw of the marks costs 15-30 ms and events asked for it in dozens, also while the sheet
    was closed. Now: nothing while it is closed, and one redraw per burst of requests."""

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        lua = self.lua
        lua.execute("""
        local function Frame()
            local f = { shown = true }
            function f:RegisterEvent() end
            function f:SetScript() end
            function f:HookScript() end
            function f:IsShown() return self.shown end
            function f:IsVisible() return self.shown end
            function f:GetID() return self.id end
            function f:GetEffectiveAlpha() return 1 end
            function f:GetObjectType() return "Button" end
            return f
        end
        CreateFrame = function() return Frame() end
        timers = {}
        C_Timer = { After = function(d, fn) timers[#timers + 1] = fn end }
        NUM_CONTAINER_SCAN_FRAMES = 0
        PaperDollFrame = Frame()
        GetInventoryItemLink = function() return nil end
        contextCalls = 0
        """)
        load_addon_file(lua, self.ns, "UI/SV_UpgradeIndicatorView.lua")

        def contexts():
            lua.execute("contextCalls = contextCalls + 1")
            return lua.table(profile=lua.table(goal="RAID"))

        self.ns.GetTooltipEvaluationContexts = contexts
        self.ns.GetWornPieceInfo = lambda *args: None

    def calls(self):
        return int(self.lua.eval("contextCalls"))

    def test_a_closed_character_sheet_costs_nothing(self):
        self.lua.execute("PaperDollFrame.shown = false")
        self.ns.RefreshCatalystMarks()
        self.assertEqual(0, self.calls())
        self.lua.execute("PaperDollFrame.shown = true")
        self.ns.RefreshCatalystMarks()
        self.assertEqual(1, self.calls())

    def test_a_burst_of_requests_is_one_redraw(self):
        before = int(self.lua.eval("#timers"))
        for _ in range(8):
            self.ns.RequestCatalystMarks(0.5)
        self.assertEqual(before + 1, int(self.lua.eval("#timers")))
        self.lua.execute(f"timers[{before + 1}]()")
        self.assertEqual(1, self.calls())
        self.ns.RequestCatalystMarks(0.5)          # a new burst after the redraw is answered again
        self.assertEqual(before + 2, int(self.lua.eval("#timers")))


class StatAuditRefreshCostTests(unittest.TestCase):
    """The window rebuild (10-20 ms) is asked for by every stat event and every loadout change: one rebuild per burst."""

    def source(self):
        import pathlib
        return pathlib.Path("StatVerdict/UI/SV_StatAudit.lua").read_text(encoding="utf-8-sig")

    def test_the_refresh_request_and_the_stat_events_schedule_the_rebuild(self):
        src = self.source()
        request = src[src.index("function ns.RequestStatAuditRefresh()"):]
        request = request[:request.index("\nend") + 4]
        self.assertIn("ScheduleAuditUpdate()", request)
        self.assertNotIn("UpdateFrame()", request)
        handler = src[src.index("ns.EventFrame:SetScript(\"OnEvent\""):]
        handler = handler[:handler.index("\nend)") + 5]
        self.assertIn("ScheduleAuditUpdate()", handler)
        self.assertNotIn("UpdateFrame()", handler)

    def test_one_pending_rebuild_absorbs_the_requests_that_follow(self):
        src = self.source()
        body = src[src.index("local function ScheduleAuditUpdate()"):]
        body = body[:body.index("\nend\n") + 5]
        self.assertIn("if auditUpdatePending then return end", body)
        self.assertIn("auditUpdatePending = false", body)
