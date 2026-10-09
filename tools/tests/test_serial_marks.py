"""Marks know their piece by the game's serial number (item GUID); Auto mark keeps the marks of the played spec in step with
what is worn; a mark made by hand stays until the player moves on."""
import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime

SETUP = r"""
chat, equipCalls, pickups, cursorEquips = {}, {}, {}, {}
DEFAULT_CHAT_FRAME = { AddMessage = function(_, text) chat[#chat + 1] = text end }
INVSLOT_MAINHAND, INVSLOT_OFFHAND = 16, 17
clock, SPEC = 100, 200
GetTime = function() return clock end
InCombatLockdown = function() return false end
GetSpecialization = function() return 1 end
GetSpecializationInfo = function(i) return SPEC end
GetSpecializationInfoByID = function(id) return id, "Spec" .. id end
UnitGUID = function() return "Player-1-ME" end
worn, wornGUID, bag, bagGUID = {}, {}, {}, {}     -- slot -> link ; slot -> serial ; list of links ; list of serials
GetInventoryItemLink = function(unit, slot) return worn[slot] end
C_Container = {
    GetContainerNumSlots = function(b) if b == 0 then return #bag end return 0 end,
    GetContainerItemLink = function(b, s) return bag[s] end,
    PickupContainerItem = function(b, s) pickups[#pickups + 1] = { b, s } end,
}
ItemLocation = {
    CreateFromEquipmentSlot = function(_, slot) return { eq = slot } end,
    CreateFromBagAndSlot = function(_, b, s) return { bag = b, slot = s } end,
}
C_Item = {
    EquipItemByName = function(link, slot) equipCalls[#equipCalls + 1] = { link, slot } end,
    GetItemGUID = function(location)
        if location.eq then return wornGUID[location.eq] end
        return bagGUID[location.slot]
    end,
}
EquipCursorItem = function(slot) cursorEquips[#cursorEquips + 1] = slot end
CursorHasItem = function() return false end
CreateFrame = function() return { RegisterEvent = function() end, SetScript = function() end } end
C_Timer = { After = function() end }
StatVerdictDB = { specSnapshots = { version = 1, revision = 0, bySpecID = {
    ["200"] = { specID = 200, revision = 1, characterGUID = "Player-1-ME", equipment = {} },
} } }
"""

NECK = "|Hitem:111::|h[Neck]|h"
NECK_B = "|Hitem:112::|h[Neck B]|h"
RING = "|Hitem:301::|h[Ring]|h"


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class SerialMarkTests(unittest.TestCase):
    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        g = self.lua.globals()
        g.NECK, g.NECK_B, g.RING = NECK, NECK_B, RING

    def snap(self, field):
        return self.lua.eval(f'StatVerdictDB.specSnapshots.bySpecID["200"].{field}')

    def calls(self):
        return [(str(self.lua.eval(f"equipCalls[{i}][1]")), int(self.lua.eval(f"equipCalls[{i}][2]")))
                for i in range(1, int(self.lua.eval("#equipCalls")) + 1)]

    def approve(self, link, slot, serial):
        profile = self.lua.eval("{ specID = 200, specName = 'Spec200' }")
        return self.ns.ApproveItemIntoVirtualLoadout(link, profile, slot, serial)

    # ---- the serial number is saved with the mark, and the piece is found by it

    def test_a_mark_made_in_the_bags_keeps_the_serial_number(self):
        self.approve(NECK, 2, "Item-A")
        self.assertEqual("Item-A", str(self.snap('markedGUID["2"]')))

    def test_the_marked_copy_is_put_on_not_another_copy_of_the_item(self):
        self.lua.execute('bag = { NECK, NECK }; bagGUID = { "Item-A", "Item-B" }; '
                         'worn[2] = NECK_B; wornGUID[2] = "Item-OLD"')
        self.approve(NECK, 2, "Item-B")
        self.assertEqual(1, self.ns.EquipMarkedLoadoutItems())
        # Two copies in the bags: the exact one (bag slot 2) is picked up and dropped on the slot.
        self.assertEqual("2", str(self.lua.eval("pickups[1][2]")))
        self.assertEqual("2", str(self.lua.eval("cursorEquips[1]")))
        self.assertEqual([], self.calls())

    def test_a_single_copy_is_put_on_by_its_item(self):
        self.lua.execute('bag = { NECK }; bagGUID = { "Item-A" }; worn[2] = NECK_B; wornGUID[2] = "Item-OLD"')
        self.approve(NECK, 2, "Item-A")
        self.assertEqual(1, self.ns.EquipMarkedLoadoutItems())
        self.assertEqual([(NECK, 2)], self.calls())

    def test_a_serial_that_is_not_in_the_bags_puts_on_nothing(self):
        # Same item in the bags, but it is another copy: the mark is about the one that is gone.
        self.lua.execute('bag = { NECK }; bagGUID = { "Item-OTHER" }; worn[2] = NECK_B; wornGUID[2] = "Item-OLD"')
        self.approve(NECK, 2, "Item-A")
        self.assertEqual(0, self.ns.EquipMarkedLoadoutItems())
        self.assertEqual([], self.calls())

    def test_nothing_to_do_when_the_marked_piece_is_already_worn(self):
        self.lua.execute('bag = {}; worn[2] = NECK; wornGUID[2] = "Item-A"')
        self.approve(NECK, 2, "Item-A")
        self.assertEqual(0, self.ns.EquipMarkedLoadoutItems())

    def test_the_loadout_knows_which_copy_is_in_it(self):
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].equipment = { ["11"] = RING }; '
                         'StatVerdictDB.specSnapshots.bySpecID["200"].markedGUID = { ["11"] = "Item-A" }')
        profile = self.lua.eval("{ specID = 200 }")
        self.assertTrue(self.ns.IsItemInEquipmentSnapshot(profile, RING, "Item-A")[0])
        self.assertFalse(self.ns.IsItemInEquipmentSnapshot(profile, RING, "Item-B"))   # another copy of the same item
        self.assertTrue(self.ns.IsItemInEquipmentSnapshot(profile, RING)[0])           # no serial known: by item, as before

    def test_a_marked_piece_is_still_the_marked_piece_after_an_upgrade_changed_its_level(self):
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].equipment = { ["11"] = RING }; '
                         'StatVerdictDB.specSnapshots.bySpecID["200"].markedGUID = { ["11"] = "Item-A" }')
        profile = self.lua.eval("{ specID = 200 }")
        upgraded = "|Hitem:301::bonus:9|h[Ring]|h"
        self.assertTrue(self.ns.IsItemInEquipmentSnapshot(profile, upgraded, "Item-A")[0])


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AutoMarkTests(unittest.TestCase):
    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        g = self.lua.globals()
        g.NECK, g.NECK_B, g.RING = NECK, NECK_B, RING
        self.lua.execute('worn[2] = NECK; wornGUID[2] = "Item-A"')

    def snap(self, field):
        return self.lua.eval(f'StatVerdictDB.specSnapshots.bySpecID["200"].{field}')

    def approve(self, link, slot, serial):
        profile = self.lua.eval("{ specID = 200, specName = 'Spec200' }")
        return self.ns.ApproveItemIntoVirtualLoadout(link, profile, slot, serial)

    def test_what_is_worn_is_marked_with_its_serial_number(self):
        self.assertEqual(1, self.ns.AutoMarkWornPieces())
        self.assertIn("item:111", str(self.snap('marked["2"]')))
        self.assertEqual("Item-A", str(self.snap('markedGUID["2"]')))

    def test_nothing_changes_when_nothing_new_is_worn(self):
        self.ns.AutoMarkWornPieces()
        self.assertEqual(0, self.ns.AutoMarkWornPieces())

    def test_a_replaced_piece_loses_its_mark_the_new_one_takes_it(self):
        self.ns.AutoMarkWornPieces()
        self.lua.execute('worn[2] = NECK_B; wornGUID[2] = "Item-B"')
        self.assertEqual(1, self.ns.AutoMarkWornPieces())
        self.assertEqual("Item-B", str(self.snap('markedGUID["2"]')))
        self.assertIn("item:112", str(self.snap('marked["2"]')))

    def test_a_loadout_without_a_snapshot_is_left_alone(self):
        self.lua.execute("SPEC = 999")
        self.assertEqual(0, self.ns.AutoMarkWornPieces())

    def test_nothing_in_combat(self):
        self.lua.execute("InCombatLockdown = function() return true end")
        self.assertEqual(0, self.ns.AutoMarkWornPieces())

    def test_switched_off_in_the_options_it_marks_nothing(self):
        self.lua.execute("StatVerdictDB.autoMark = false")
        self.assertEqual(0, self.ns.AutoMarkWornPieces())
        self.assertIsNone(self.snap("marked"))
        self.assertFalse(self.ns.IsAutoMarkOn())

    def test_the_click_names_follow_the_option(self):
        self.assertEqual("Alt-Click", str(self.ns.MarkClickLabel(True)))
        self.lua.execute("StatVerdictDB.autoMark = false")
        self.assertEqual("Alt-Left-Click", str(self.ns.MarkClickLabel(True)))
        self.assertEqual("Alt-Right-Click", str(self.ns.MarkClickLabel(False)))

    # ---- a mark made by hand

    def test_a_hand_mark_is_not_replaced_while_the_worn_piece_stays(self):
        self.ns.AutoMarkWornPieces()
        self.lua.execute("bag = { NECK_B }; bagGUID = { 'Item-B' }")
        self.approve(NECK_B, 2, "Item-B")
        self.ns.AutoMarkWornPieces()
        self.assertEqual("Item-B", str(self.snap('markedGUID["2"]')))

    def test_a_hand_mark_lets_go_when_another_piece_is_worn_in_the_slot(self):
        self.ns.AutoMarkWornPieces()
        self.lua.execute("bag = { NECK_B }; bagGUID = { 'Item-B' }")
        self.approve(NECK_B, 2, "Item-B")
        self.lua.execute('worn[2] = RING; wornGUID[2] = "Item-C"')
        self.ns.AutoMarkWornPieces()
        self.assertEqual("Item-C", str(self.snap('markedGUID["2"]')))   # the player moved on: the worn piece is the mark

    def test_a_hand_mark_becomes_an_ordinary_mark_once_the_piece_is_worn(self):
        self.ns.AutoMarkWornPieces()
        self.lua.execute("bag = { NECK_B }; bagGUID = { 'Item-B' }")
        self.approve(NECK_B, 2, "Item-B")
        self.lua.execute('worn[2] = NECK_B; wornGUID[2] = "Item-B"; bag = {}; bagGUID = {}')
        self.ns.AutoMarkWornPieces()
        self.assertEqual("Item-B", str(self.snap('markedGUID["2"]')))
        self.lua.execute('worn[2] = NECK; wornGUID[2] = "Item-A"')
        self.assertEqual(1, self.ns.AutoMarkWornPieces())   # no longer locked: the next piece worn takes the slot
        self.assertEqual("Item-A", str(self.snap('markedGUID["2"]')))

    def test_marks_made_before_auto_mark_existed_keep_a_piece_that_sits_in_the_bags(self):
        # A mark whose piece is in the bags (not worn) is the player's own choice.
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].marked = { ["2"] = NECK_B }; bag = { NECK_B }')
        self.ns.AutoMarkWornPieces()
        self.assertIn("item:112", str(self.snap('marked["2"]')))

    def test_a_two_hander_clears_the_off_hand_mark(self):
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].marked = { ["17"] = RING }')
        self.lua.execute('worn = { [16] = "|Hitem:500::|h[Greataxe]|h" }; wornGUID = { [16] = "Item-W" }')
        self.ns.GetItemEquipLocation = self.lua.eval("function() return 'INVTYPE_2HWEAPON' end")
        self.ns.AutoMarkWornPieces()
        self.assertIsNone(self.snap('marked["17"]'))


RING_UP = "|Hitem:301::bonus:9|h[Ring]|h"   # the same ring after an upgrade


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class SerialChangeTests(unittest.TestCase):
    """An upgrade can give a piece a new serial number: the marks follow it and the old -> new pair is remembered."""

    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.lua.execute("""
        itemCount, levels = 1, {}
        C_Item.GetItemCount = function(id) return itemCount end
        C_Item.GetDetailedItemLevelInfo = function(link) return levels[link] end
        """)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        g = self.lua.globals()
        g.RING, g.RING_UP = RING, RING_UP
        self.lua.execute("""
        local snap = StatVerdictDB.specSnapshots.bySpecID["200"]
        snap.equipment = { ["11"] = RING }
        snap.marked = { ["11"] = RING }
        snap.markedGUID = { ["11"] = "Item-OLD" }
        snap.manualSlots = { ["11"] = "Item-OLD" }
        StatVerdictDB.specSnapshots.bySpecID["201"] = { specID = 201, revision = 1, characterGUID = "Player-1-ME",
            equipment = { ["11"] = RING }, marked = { ["11"] = RING }, markedGUID = { ["11"] = "Item-OLD" } }
        bag = { RING_UP }; bagGUID = { "Item-NEW" }
        """)

    def field(self, spec, path):
        return self.lua.eval(f'StatVerdictDB.specSnapshots.bySpecID["{spec}"].{path}')

    def test_the_marks_of_every_loadout_move_to_the_new_serial_number(self):
        self.lua.execute("levels[RING] = 290; levels[RING_UP] = 296")
        self.assertEqual(1, self.ns.ReconcileMarkedSerials())
        for spec in ("200", "201"):
            self.assertEqual("Item-NEW", str(self.field(spec, 'markedGUID["11"]')))
            self.assertIn("bonus:9", str(self.field(spec, 'marked["11"]')))
        self.assertEqual("Item-NEW", str(self.field("200", 'manualSlots["11"]')))
        self.assertEqual("Item-NEW", str(self.lua.eval("StatVerdictDB.serialHistory['Item-OLD']")))

    def test_the_loadout_still_holds_the_piece_whichever_number_is_asked(self):
        self.lua.execute("StatVerdictDB.serialHistory = { ['Item-OLD'] = 'Item-NEW' }")
        profile = self.lua.eval("{ specID = 200 }")
        self.assertTrue(self.ns.IsItemInEquipmentSnapshot(profile, RING_UP, "Item-NEW")[0])

    def test_nothing_changes_while_the_marked_piece_is_still_here(self):
        self.lua.execute("bag = { RING, RING_UP }; bagGUID = { 'Item-OLD', 'Item-NEW' }")
        self.assertEqual(0, self.ns.ReconcileMarkedSerials())
        self.assertEqual("Item-OLD", str(self.field("200", 'markedGUID["11"]')))

    def test_a_copy_kept_in_the_bank_is_not_mistaken_for_the_gone_piece(self):
        self.lua.execute("itemCount = 2")   # one here, one somewhere else: the marked one may be in the bank
        self.assertEqual(0, self.ns.ReconcileMarkedSerials())

    def test_a_piece_of_a_lower_level_is_not_an_upgrade(self):
        self.lua.execute("levels[RING] = 296; levels[RING_UP] = 290")
        self.assertEqual(0, self.ns.ReconcileMarkedSerials())

    def test_two_unmarked_copies_are_ambiguous_and_left_alone(self):
        self.lua.execute("bag = { RING_UP, RING_UP }; bagGUID = { 'Item-NEW', 'Item-NEW2' }; itemCount = 2")
        self.assertEqual(0, self.ns.ReconcileMarkedSerials())

    def test_another_characters_loadouts_are_not_touched(self):
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].characterGUID = "Player-1-OTHER"; '
                         'StatVerdictDB.specSnapshots.bySpecID["201"].characterGUID = "Player-1-OTHER"')
        self.assertEqual(0, self.ns.ReconcileMarkedSerials())

    def test_nothing_in_combat(self):
        self.lua.execute("InCombatLockdown = function() return true end")
        self.assertEqual(0, self.ns.ReconcileMarkedSerials())


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class MarkBothBuildsTests(unittest.TestCase):
    """A worn piece that replaces a marked one and is an upgrade for the other build too is saved for that build as well."""

    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.lua.execute("""
        StatVerdictDB.specSnapshots.bySpecID["201"] = { specID = 201, revision = 1, characterGUID = "Player-1-ME",
            equipment = { ["2"] = "|Hitem:900::|h[OtherBuildNeck]|h" }, marked = {}, markedGUID = {} }
        UPGRADE, OTHER_SLOT = true, 2
        """)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        g = self.lua.globals()
        g.NECK, g.NECK_B = NECK, NECK_B
        lua = self.lua
        self.ns.GetTooltipEvaluationContexts = lua.eval(
            "function() return { profile = { specID = 200 } }, { profile = { specID = 201 } } end")
        self.ns.ShouldUseEquipmentSnapshot = lua.eval("function(profile) return profile.specID ~= 200 end")
        self.ns.BuildComparison = lua.eval(
            "function(link, profile) return { selected = { isUpgrade = UPGRADE, deltaScore = 5, slotID = OTHER_SLOT } } end")
        lua.execute('worn[2] = NECK; wornGUID[2] = "Item-A"')
        self.ns.AutoMarkWornPieces()   # the first marking of the slot: nothing is saved for the other build
        lua.execute('worn[2] = NECK_B; wornGUID[2] = "Item-B"')

    def other(self, field):
        return self.lua.eval(f'StatVerdictDB.specSnapshots.bySpecID["201"].{field}')

    def test_the_first_marking_of_a_slot_leaves_the_other_build_alone(self):
        self.assertIsNone(self.other('markedGUID["2"]'))

    def test_a_piece_put_on_into_an_empty_slot_is_saved_for_both_too(self):
        self.lua.execute('OTHER_SLOT = 3; worn[3] = "|Hitem:777::|h[Cloak]|h"; wornGUID[3] = "Item-C"')
        self.ns.AutoMarkWornPieces()
        self.assertEqual("Item-C", str(self.other('markedGUID["3"]')))

    def test_the_very_first_pass_leaves_the_other_build_alone(self):
        # Pre-existing gear is only marked for the spec that is played: an update never rewrites the other build.
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].autoMarkSeeded = nil; '
                         'StatVerdictDB.specSnapshots.bySpecID["200"].markedGUID = {}; '
                         'StatVerdictDB.specSnapshots.bySpecID["200"].marked = {}')
        self.ns.AutoMarkWornPieces()
        self.assertIsNone(self.other('markedGUID["2"]'))

    def test_a_replacing_piece_that_is_an_upgrade_for_both_is_saved_for_both(self):
        self.ns.AutoMarkWornPieces()
        self.assertEqual("Item-B", str(self.other('markedGUID["2"]')))
        self.assertIn("item:112", str(self.other('marked["2"]')))
        self.assertIn("item:112", str(self.other('equipment["2"]')))

    def test_nothing_when_it_is_no_upgrade_for_the_other_build(self):
        self.lua.execute("UPGRADE = false")
        self.ns.AutoMarkWornPieces()
        self.assertIsNone(self.other('markedGUID["2"]'))

    def test_a_hand_mark_of_the_other_build_wins(self):
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["201"].manualSlots = { ["2"] = true }; '
                         'StatVerdictDB.specSnapshots.bySpecID["201"].markedGUID = { ["2"] = "Item-HAND" }')
        self.ns.AutoMarkWornPieces()
        self.assertEqual("Item-HAND", str(self.other('markedGUID["2"]')))

    def test_nothing_without_a_second_build(self):
        self.ns.GetTooltipEvaluationContexts = self.lua.eval("function() return { profile = { specID = 200 } }, nil end")
        self.ns.AutoMarkWornPieces()
        self.assertIsNone(self.other('markedGUID["2"]'))


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WornArrowTests(unittest.TestCase):
    """The red arrow on the character sheet: only for a slot that has a piece worn in it."""

    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute("""
        InCombatLockdown = function() return false end
        bag, wornGUID = { "|Hitem:301::|h[Ring]|h" }, {}
        C_Container = {
            GetContainerNumSlots = function(b) if b == 0 then return #bag end return 0 end,
            GetContainerItemLink = function(b, s) return bag[s] end,
        }
        C_Item = { IsEquippableItem = function() return true end }
        """)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_UpgradeIndicatorLogic.lua")
        lua = self.lua
        self.ns.GetTooltipEvaluationContexts = lua.eval("function() return { specID = 200, profile = { specID = 200 } }, nil end")
        self.ns.ShouldUseEquipmentSnapshot = lua.eval("function(profile) return false end")
        self.ns.BuildComparison = lua.eval(
            "function(link, profile) return { selected = { isUpgrade = true, deltaScore = 9, slotID = 11 } } end")
        self.ns.GetWornItemGUID = lua.eval("function(slot) return wornGUID[slot] end")

    def test_a_worn_piece_that_a_bag_piece_beats_gets_the_warning(self):
        self.lua.execute('wornGUID[11] = "Item-A"')
        entry = self.ns.GetBagUpgradesForWornSlots()[11]
        self.assertEqual(9, entry["gain"])
        self.assertFalse(entry["ignored"])

    def test_an_empty_slot_gets_no_warning(self):
        self.assertIsNone(self.ns.GetBagUpgradesForWornSlots()[11])

    def test_the_warning_can_be_ignored_and_is_forgotten_when_the_piece_is_taken_off(self):
        self.lua.execute('wornGUID[11] = "Item-A"; StatVerdictDB = {}')
        self.assertTrue(self.ns.IgnoreWornWarning(11))
        self.assertTrue(self.ns.GetBagUpgradesForWornSlots()[11]["ignored"])
        self.lua.execute("wornGUID[11] = nil")
        self.ns.PruneIgnoredWornWarnings()
        self.lua.execute('wornGUID[11] = "Item-A"')
        self.ns.ClearWornUpgradeCache()
        self.assertFalse(self.ns.GetBagUpgradesForWornSlots()[11]["ignored"])


if __name__ == "__main__":
    unittest.main()
