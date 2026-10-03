"""Switching spec puts on the pieces the player marked for the new spec; everything else stays as worn."""
import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime

SETUP = r"""
chat, equipCalls = {}, {}
DEFAULT_CHAT_FRAME = { AddMessage = function(_, text) chat[#chat + 1] = text end }
INVSLOT_MAINHAND, INVSLOT_OFFHAND = 16, 17
clock, SPEC = 100, 100
GetTime = function() return clock end
InCombatLockdown = function() return false end
GetSpecialization = function() return 1 end
GetSpecializationInfo = function(i) return SPEC end
GetSpecializationInfoByID = function(id) return id, "Spec" .. id end
UnitGUID = function() return "Player-1-ME" end
worn, bag = {}, {}                                  -- slotID -> link ; list of links in the bags
GetInventoryItemLink = function(unit, slot) return worn[slot] end
C_Container = {
    GetContainerNumSlots = function(b) if b == 0 then return #bag end return 0 end,
    GetContainerItemLink = function(b, s) return bag[s] end,
}
C_Item = { EquipItemByName = function(link, slot) equipCalls[#equipCalls + 1] = { link, slot } end }
CreateFrame = function() return { RegisterEvent = function() end, SetScript = function() end } end
C_Timer = { After = function() end }
StatVerdictDB = { specSnapshots = { version = 1, revision = 0, bySpecID = {
    ["200"] = { specID = 200, revision = 1, characterGUID = "Player-1-ME",
        equipment = { ["2"] = "|Hitem:111::|h[Neck]|h", ["16"] = "|Hitem:222::|h[Axe]|h" },
        marked = { ["2"] = "|Hitem:111::|h[Neck]|h" } },
} } }
"""


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class EquipMarkedLoadoutTests(unittest.TestCase):
    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        self.lua.execute('SPEC = 200; worn[2] = "|Hitem:999::|h[OldNeck]|h"; worn[16] = "|Hitem:555::|h[Sword]|h"; '
                         'bag = { "|Hitem:111::|h[Neck]|h", "|Hitem:222::|h[Axe]|h" }')

    def calls(self):
        return [(str(self.lua.eval(f"equipCalls[{i}][1]")), int(self.lua.eval(f"equipCalls[{i}][2]")))
                for i in range(1, int(self.lua.eval("#equipCalls")) + 1)]

    def test_only_the_marked_piece_is_put_on_the_rest_stays(self):
        self.assertEqual(1, self.ns.EquipMarkedLoadoutItems())
        calls = self.calls()
        self.assertEqual([2], [slot for _, slot in calls])   # the Axe was never marked: the worn sword stays
        self.assertIn("item:111", calls[0][0])
        self.assertEqual(1, int(self.lua.eval("#chat")))

    def test_already_worn_means_nothing_to_do(self):
        self.lua.execute('worn[2] = "|Hitem:111::|h[Neck]|h"')
        self.assertEqual(0, self.ns.EquipMarkedLoadoutItems())

    def test_a_marked_piece_that_is_not_in_the_bags_is_skipped(self):
        self.lua.execute("bag = {}")
        self.assertEqual(0, self.ns.EquipMarkedLoadoutItems())
        self.assertEqual([], self.calls())

    def test_nothing_in_combat(self):
        self.lua.execute("InCombatLockdown = function() return true end")
        self.assertEqual(0, self.ns.EquipMarkedLoadoutItems())
        self.assertEqual([], self.calls())

    def test_a_loadout_without_marks_changes_nothing(self):
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].marked = nil')
        self.assertEqual(0, self.ns.EquipMarkedLoadoutItems())

    def test_approve_marks_the_slot_and_remove_clears_it(self):
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].marked = nil')
        self.ns.GetItemEquipLocation = self.lua.eval("function() return 'INVTYPE_NECK' end")
        profile = self.lua.eval("{ specID = 200, specName = 'Spec200' }")
        self.ns.GetProfileSpecID = self.lua.eval("function() return 200 end")
        ok = self.ns.ApproveItemIntoVirtualLoadout("|Hitem:111::|h[Neck]|h", profile, 2)
        self.assertTrue(ok[0] if hasattr(ok, "__getitem__") else ok)
        self.assertIn("item:111", str(self.lua.eval('StatVerdictDB.specSnapshots.bySpecID["200"].marked["2"]')))
        self.ns.RemoveItemFromVirtualLoadout("|Hitem:111::|h[Neck]|h", profile)
        self.assertIsNone(self.lua.eval('StatVerdictDB.specSnapshots.bySpecID["200"].marked["2"]'))


if __name__ == "__main__":
    unittest.main()
