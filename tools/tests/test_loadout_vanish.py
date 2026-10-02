"""A saved loadout drops an item that is gone for good, falls back to the worn gear, and takes it back after a buyback."""
import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime

SETUP = r"""
chat = {}
DEFAULT_CHAT_FRAME = { AddMessage = function(_, text) chat[#chat + 1] = text end }
INVSLOT_MAINHAND, INVSLOT_OFFHAND = 16, 17
clock = 100
GetTime = function() return clock end
InCombatLockdown = function() return false end
GetSpecialization = function() return 1 end
GetSpecializationInfo = function(i) return 100 end            -- the active spec is 100
GetSpecializationInfoByID = function(id) return id, "Spec" .. id end
owned = {}                                                    -- itemID -> count
C_Item = { GetItemCount = function(id) return owned[id] or 0 end }
worn = {}                                                     -- slotID -> link
GetInventoryItemLink = function(unit, slot) return worn[slot] end
CreateFrame = function() return { RegisterEvent = function() end, SetScript = function() end } end
C_Timer = { After = function() end }
StatVerdictDB = { specSnapshots = { version = 1, revision = 0, bySpecID = {
    ["200"] = { specID = 200, revision = 1, equipment = { ["2"] = "|Hitem:111::|h[Thorny]|h", ["16"] = "|Hitem:222::|h[Axe]|h" } },
    ["100"] = { specID = 100, revision = 1, equipment = { ["2"] = "|Hitem:111::|h[Thorny]|h" } },
} } }
"""


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class LoadoutVanishTests(unittest.TestCase):
    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")

    def run_check(self):
        return self.ns.PruneVanishedLoadoutItems()

    def slot(self, spec, slot):
        return self.lua.eval(f'StatVerdictDB.specSnapshots.bySpecID["{spec}"].equipment["{slot}"]')

    def test_owned_items_stay(self):
        self.lua.execute("owned[111] = 1; owned[222] = 1")
        self.run_check()
        self.lua.execute("clock = clock + 10")
        self.assertEqual(self.run_check()[0], 0)
        self.assertIn("111", self.slot(200, 2))

    def test_gone_item_needs_two_looks_then_falls_back_to_the_worn_one(self):
        self.lua.execute('owned[222] = 1; worn[2] = "|Hitem:333::|h[Worn]|h"')
        changed, pending = self.run_check()          # first look: missing, not removed yet
        self.assertEqual((changed, pending), (0, True))
        self.assertIn("111", self.slot(200, 2))
        self.lua.execute("clock = clock + 4")
        changed, _ = self.run_check()                # second look: gone for good
        self.assertEqual(changed, 1)
        self.assertIn("333", self.slot(200, 2))      # what is worn now has priority
        self.assertEqual(self.lua.eval("#chat"), 1)
        self.assertIn("removed from the Spec200", self.lua.eval("chat[1]"))

    def test_nothing_worn_leaves_the_slot_empty(self):
        self.lua.execute("owned[222] = 1")
        self.run_check()
        self.lua.execute("clock = clock + 4")
        self.run_check()
        self.assertIsNone(self.slot(200, 2))

    def test_the_active_spec_is_not_touched(self):
        self.run_check()
        self.lua.execute("clock = clock + 4")
        self.run_check()
        self.assertIn("111", self.slot(100, 2))

    def test_an_item_that_comes_back_in_time_is_not_removed(self):
        self.lua.execute("owned[222] = 1")
        self.run_check()
        self.lua.execute("owned[111] = 1; clock = clock + 4")   # was only missing for a moment (a move)
        self.assertEqual(self.run_check()[0], 0)
        self.assertIn("111", self.slot(200, 2))

    def test_a_buyback_puts_it_back(self):
        self.lua.execute("owned[222] = 1")
        self.run_check()
        self.lua.execute("clock = clock + 4")
        self.run_check()                              # removed
        self.assertIsNone(self.slot(200, 2))
        self.lua.execute("owned[111] = 1; clock = clock + 30")
        self.assertEqual(self.run_check()[0], 1)
        self.assertIn("111", self.slot(200, 2))

    def test_a_buyback_after_the_slot_changed_does_not_overwrite_it(self):
        self.lua.execute("owned[222] = 1")
        self.run_check()
        self.lua.execute("clock = clock + 4")
        self.run_check()
        self.lua.execute('StatVerdictDB.specSnapshots.bySpecID["200"].equipment["2"] = "|Hitem:444::|h[New]|h"; owned[111] = 1; clock = clock + 30; owned[444] = 1')
        self.run_check()
        self.assertIn("444", self.slot(200, 2))

    def test_the_restore_window_ends(self):
        self.lua.execute("owned[222] = 1")
        self.run_check()
        self.lua.execute("clock = clock + 4")
        self.run_check()
        self.lua.execute("owned[111] = 1; clock = clock + 700")
        self.assertEqual(self.run_check()[0], 0)
        self.assertIsNone(self.slot(200, 2))

    def test_no_check_in_combat_or_without_a_known_spec(self):
        self.lua.execute("InCombatLockdown = function() return true end")
        self.assertEqual(self.run_check()[0], 0)
        self.lua.execute("InCombatLockdown = function() return false end; GetSpecialization = function() return nil end")
        self.assertEqual(self.run_check()[0], 0)


if __name__ == "__main__":
    unittest.main()
