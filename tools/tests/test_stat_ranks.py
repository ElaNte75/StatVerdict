"""Stat ranks on item tooltips: the place of each secondary stat in the guide's order ("+73 Critical Strike #1")."""
from __future__ import annotations

import unittest

from tools import item_check_verdict as v

CRIT, HASTE = "ITEM_MOD_CRIT_RATING_SHORT", "ITEM_MOD_HASTE_RATING_SHORT"
MASTERY, VERS = "ITEM_MOD_MASTERY_RATING_SHORT", "ITEM_MOD_VERSATILITY"


class StatRankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = v.load_addon()

    def ranks(self, order: list[str], groups: list[list[int]]) -> dict[str, tuple[int, bool]]:
        found = self.ns.GetSecondaryDisplayRanks(self.lua.table_from(order), self.lua.table_from([self.lua.table_from(g) for g in groups]))
        return {str(key): (int(found[key].rank), bool(found[key].tied)) for key in found.keys()}

    def test_the_order_is_the_rank(self) -> None:
        self.assertEqual(
            {CRIT: (1, False), HASTE: (2, False), MASTERY: (3, False), VERS: (4, False)},
            self.ranks([CRIT, HASTE, MASTERY, VERS], []),
        )

    def test_equal_stats_share_the_highest_place_of_their_group(self) -> None:
        # Blood Death Knight (Deathbringer): Crit > Mastery = Versatility > Haste
        self.assertEqual(
            {CRIT: (1, False), MASTERY: (2, True), VERS: (2, True), HASTE: (4, False)},
            self.ranks([CRIT, MASTERY, VERS, HASTE], [[2, 3]]),
        )

    def test_two_separate_groups(self) -> None:
        self.assertEqual(
            {HASTE: (1, True), VERS: (1, True), CRIT: (3, True), MASTERY: (3, True)},
            self.ranks([HASTE, VERS, CRIT, MASTERY], [[1, 2], [3, 4]]),
        )

    def test_nothing_without_an_order(self) -> None:
        self.assertEqual({}, self.ranks([], []))

    # ---- the tooltip ------------------------------------------------------------------------------------------------

    def tooltip(self, lines: list[str], *, order=None, groups=None, combat: bool = False, off: bool = False,
                view: str = "MAIN", alt: bool = False, off_spec_order=None):
        """off: the switch is off. view: the build selected in the window. alt: Alt is held. off_spec_order: the
        Off Spec build's stat order (None: no Off Spec is selected)."""
        order = order or [CRIT, MASTERY, VERS, HASTE]
        groups = groups if groups is not None else [[2, 3]]
        lua = self.lua
        lua.globals().SV_RANK_LINES = lua.table_from(lines)
        lua.globals().SV_RANK_ORDER = lua.table_from(order)
        lua.globals().SV_RANK_GROUPS = lua.table_from([lua.table_from(g) for g in groups])
        lua.globals().SV_RANK_OFF_ORDER = lua.table_from(off_spec_order) if off_spec_order else None
        lua.execute(f"""
        ITEM_MOD_CRIT_RATING_SHORT, ITEM_MOD_HASTE_RATING_SHORT = "Critical Strike", "Haste"
        ITEM_MOD_MASTERY_RATING_SHORT, ITEM_MOD_VERSATILITY = "Mastery", "Versatility"
        ITEM_DELTA_DESCRIPTION = "If you replace this item, the following stat changes will occur:"
        InCombatLockdown = function() return {str(combat).lower()} end
        IsAltKeyDown = function() return {str(alt).lower()} end
        StatVerdictDB = {{ showStatRanks = {"false" if off else "nil"} }}
        local count = #SV_RANK_LINES
        for i = 1, count do
            _G["RankTipTextLeft" .. i] = {{ t = SV_RANK_LINES[i], GetText = function(s) return s.t end, SetText = function(s, x) s.t = x end }}
        end
        for i = count + 1, count + 20 do _G["RankTipTextLeft" .. i] = nil end
        RANK_TIP = {{ NumLines = function() return count end, GetName = function() return "RankTip" end, Show = function() RANK_TIP.shown = true end }}
        SV_RANK_PROFILE = {{ secondaryOrder = SV_RANK_ORDER, equalGroups = SV_RANK_GROUPS }}
        SV_RANK_OFF_PROFILE = SV_RANK_OFF_ORDER and {{ secondaryOrder = SV_RANK_OFF_ORDER, equalGroups = {{}} }} or nil
        SV_TEST_NS.GetTooltipEvaluationContexts = function()
            return {{ profile = SV_RANK_PROFILE }}, SV_RANK_OFF_PROFILE and {{ profile = SV_RANK_OFF_PROFILE }} or nil
        end
        SV_TEST_NS.GetStatAuditActiveView = function() return "{view}" end
        """)
        self.ns.AddStatRanksToTooltip(lua.eval("RANK_TIP"))
        return [str(lua.eval(f"RankTipTextLeft{i}.t")) for i in range(1, len(lines) + 1)], bool(lua.eval("RANK_TIP.shown"))

    ITEM = ["Aged Interwoven Scaleplate", "+94 Strength", "+73 Critical Strike", "+67 Versatility", "+54 Haste", "+40 Mastery"]

    def test_every_secondary_stat_line_gets_its_place(self) -> None:
        text, shown = self.tooltip(self.ITEM)
        self.assertTrue(shown)
        self.assertEqual("Aged Interwoven Scaleplate", text[0])
        self.assertEqual("+94 Strength", text[1])  # the primary stat is not ranked
        self.assertTrue(text[2].endswith("|cffff8000#1|r |TInterface\AddOns\StatVerdict\Textures\StatRankMS:8:16|t"))
        self.assertIn("#2", text[3])  # Versatility and Mastery are equal: the same number
        self.assertIn("#4", text[4])
        self.assertIn("#2", text[5])

    def test_equal_stats_just_share_the_number(self) -> None:
        text, _ = self.tooltip(["+54 Mastery", "+67 Versatility"])
        for line in text:
            self.assertIn("#2", line)
            self.assertNotIn("=", line)
            self.assertNotIn("(", line)

    def test_the_build_label_comes_after_the_number(self) -> None:
        text, _ = self.tooltip(["+73 Critical Strike"])
        self.assertLess(text[0].index("#1"), text[0].index("StatRankMS"))
        self.assertTrue(text[0].endswith("|t"))

    def test_the_build_shown_is_named_ms_by_default(self) -> None:
        text, _ = self.tooltip(["+73 Critical Strike"])
        self.assertIn("StatRankMS", text[0])
        self.assertNotIn("StatRankOS", text[0])

    def test_with_the_off_spec_selected_in_the_window_the_tooltip_shows_it(self) -> None:
        text, _ = self.tooltip(["+73 Critical Strike", "+54 Haste"], view="OFF", off_spec_order=[HASTE, CRIT, MASTERY, VERS])
        self.assertIn("StatRankOS", text[0])
        self.assertIn("#2", text[0])  # Off Spec: Haste first, Crit second
        self.assertIn("#1", text[1])

    def test_alt_shows_the_other_build(self) -> None:
        main_with_alt, _ = self.tooltip(["+73 Critical Strike"], alt=True, off_spec_order=[HASTE, CRIT, MASTERY, VERS])
        self.assertIn("StatRankOS", main_with_alt[0])
        off_with_alt, _ = self.tooltip(["+73 Critical Strike"], view="OFF", alt=True, off_spec_order=[HASTE, CRIT, MASTERY, VERS])
        self.assertIn("StatRankMS", off_with_alt[0])
        self.assertIn("#1", off_with_alt[0])  # the Main Spec order: Crit first

    def test_alt_without_an_off_spec_changes_nothing(self) -> None:
        text, _ = self.tooltip(["+73 Critical Strike"], alt=True)
        self.assertIn("StatRankMS", text[0])

    def test_the_off_spec_view_without_an_off_spec_falls_back_to_main(self) -> None:
        text, _ = self.tooltip(["+73 Critical Strike"], view="OFF")
        self.assertIn("StatRankMS", text[0])

    def test_the_numbers_do_not_stack_when_the_tooltip_is_processed_again(self) -> None:
        text, _ = self.tooltip(self.ITEM)
        self.lua.execute("for i = 1, 6 do end")
        self.ns.AddStatRanksToTooltip(self.lua.eval("RANK_TIP"))
        again = [str(self.lua.eval(f"RankTipTextLeft{i}.t")) for i in range(1, 7)]
        self.assertEqual(text, again)

    def test_colored_lines_and_gems_are_ranked_too(self) -> None:
        text, _ = self.tooltip(["|cff00ff00+73 Critical Strike|r", "+54 Haste"])
        self.assertTrue(text[0].startswith("|cff00ff00+73 Critical Strike|r "))
        self.assertIn("#1", text[0])
        self.assertIn("#4", text[1])

    def test_effect_text_and_enchants_are_left_alone(self) -> None:
        lines = ["Equip: Increases Critical Strike by 50.", "Enchanted: +150 Haste", "+10 Haste for 15 sec", "Use: gain 673 Mastery"]
        text, shown = self.tooltip(lines)
        self.assertEqual(lines, text)
        self.assertFalse(shown)

    def test_the_comparison_block_is_left_alone(self) -> None:
        lines = ["+73 Critical Strike", "If you replace this item, the following stat changes will occur:", "+7 Critical Strike", "-5 Versatility"]
        text, _ = self.tooltip(lines)
        self.assertIn("#1", text[0])
        self.assertEqual(lines[1:], text[1:])

    def test_the_switch_turns_it_off(self) -> None:
        text, shown = self.tooltip(self.ITEM, off=True)
        self.assertEqual(self.ITEM, text)
        self.assertFalse(shown)

    def test_nothing_changes_in_combat(self) -> None:
        text, _ = self.tooltip(self.ITEM, combat=True)
        self.assertEqual(self.ITEM, text)

    def test_the_number_may_come_after_the_name(self) -> None:
        text, _ = self.tooltip(["Critical Strike +73"])
        self.assertIn("#1", text[0])


if __name__ == "__main__":
    unittest.main()
