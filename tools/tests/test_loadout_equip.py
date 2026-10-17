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


GORE = "|Hitem:301::|h[Gore]|h"        # a ring both specs keep
PHOENIX = "|Hitem:302::|h[Phoenix]|h"  # a ring marked for this spec, in the bags
PREY = "|Hitem:303::|h[Prey]|h"        # a ring that belongs to the other spec only
OTHER = "|Hitem:304::|h[Other]|h"      # one more ring that is not in this loadout


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class EquipPairSlotsTests(unittest.TestCase):
    """A marked ring / trinket / one-hand weapon goes where the worn piece is not part of the loadout."""

    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        lua = self.lua
        lua.globals().GORE, lua.globals().PHOENIX, lua.globals().PREY, lua.globals().OTHER = GORE, PHOENIX, PREY, OTHER
        lua.execute("""
        SPEC = 200
        StatVerdictDB.specSnapshots.bySpecID["200"].equipment = { ["11"] = GORE, ["12"] = PHOENIX }
        StatVerdictDB.specSnapshots.bySpecID["200"].marked = { ["12"] = PHOENIX }
        worn = {}; bag = { PHOENIX }
        """)

    def put_on(self):
        self.ns.EquipMarkedLoadoutItems()
        return [(str(self.lua.eval(f"equipCalls[{i}][1]")), int(self.lua.eval(f"equipCalls[{i}][2]")))
                for i in range(1, int(self.lua.eval("#equipCalls")) + 1)]

    def test_the_marked_ring_replaces_the_one_that_is_not_in_the_loadout_not_the_shared_one(self) -> None:
        # The rings sit the other way round than when it was marked: Gore (kept) is in slot 12 now.
        self.lua.execute("worn[11] = PREY; worn[12] = GORE")
        self.assertEqual([(PHOENIX, 11)], self.put_on())

    def test_same_result_when_the_slots_are_as_they_were_marked(self) -> None:
        self.lua.execute("worn[11] = GORE; worn[12] = PREY")
        self.assertEqual([(PHOENIX, 12)], self.put_on())

    def test_nothing_when_both_worn_rings_belong_to_the_loadout(self) -> None:
        self.lua.execute("worn[11] = GORE; worn[12] = GORE")
        self.assertEqual([], self.put_on())

    def test_nothing_when_the_marked_ring_is_already_worn_in_the_other_slot(self) -> None:
        self.lua.execute("worn[11] = PHOENIX; worn[12] = PREY")
        self.assertEqual([], self.put_on())

    def test_an_empty_slot_is_used(self) -> None:
        self.lua.execute("worn[11] = GORE")
        self.assertEqual([(PHOENIX, 12)], self.put_on())

    def test_when_neither_worn_ring_is_kept_the_marked_slot_is_used(self) -> None:
        self.lua.execute("worn[11] = PREY; worn[12] = OTHER")
        self.assertEqual([(PHOENIX, 12)], self.put_on())

    def test_two_marked_rings_fill_two_different_slots(self) -> None:
        self.lua.execute("""
        StatVerdictDB.specSnapshots.bySpecID["200"].equipment = { ["11"] = GORE, ["12"] = PHOENIX }
        StatVerdictDB.specSnapshots.bySpecID["200"].marked = { ["11"] = GORE, ["12"] = PHOENIX }
        worn[11] = PREY; worn[12] = OTHER; bag = { GORE, PHOENIX }
        """)
        calls = self.put_on()
        self.assertEqual(2, len(calls))
        self.assertEqual({11, 12}, {slot for _, slot in calls})

    def test_a_one_hand_weapon_is_a_pair_only_when_it_fits_both_hands(self) -> None:
        self.ns.GetComparableSlots = self.lua.eval("function() return { 16, 17 } end")
        self.lua.execute("""
        StatVerdictDB.specSnapshots.bySpecID["200"].equipment = { ["16"] = GORE, ["17"] = PHOENIX }
        StatVerdictDB.specSnapshots.bySpecID["200"].marked = { ["17"] = PHOENIX }
        worn[16] = PREY; worn[17] = GORE
        """)
        self.assertEqual([(PHOENIX, 16)], self.put_on())  # Gore (kept) stays in the off hand

    def test_a_shield_or_two_hander_keeps_its_own_slot(self) -> None:
        self.ns.GetComparableSlots = self.lua.eval("function() return { 17 } end")
        self.lua.execute("""
        StatVerdictDB.specSnapshots.bySpecID["200"].equipment = { ["16"] = GORE, ["17"] = PHOENIX }
        StatVerdictDB.specSnapshots.bySpecID["200"].marked = { ["17"] = PHOENIX }
        worn[16] = GORE; worn[17] = PREY
        """)
        self.assertEqual([(PHOENIX, 17)], self.put_on())


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class MarkTwoPiecesOfAPairTests(unittest.TestCase):
    """Marking a second ring (trinket, one-hand weapon) must not push the first one out of the loadout."""

    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        lua = self.lua
        lua.globals().GORE, lua.globals().PHOENIX, lua.globals().PREY = GORE, PHOENIX, PREY
        lua.execute("""
        SPEC = 200
        StatVerdictDB.specSnapshots.bySpecID["200"].equipment = {}
        StatVerdictDB.specSnapshots.bySpecID["200"].marked = {}
        """)
        # The comparison names slot 11 for every ring (the weaker worn one), like a ring marked while two rings are worn.
        self.ns.GetComparableSlots = lua.eval("function() return { 11, 12 } end")
        self.ns.GetItemEquipLocation = lua.eval("function() return 'INVTYPE_FINGER' end")
        self.ns.IsItemCompatibleWithSlot = lua.eval("function() return true end")
        self.profile = lua.eval("{ specID = 200, specName = 'Spec200' }")

    def mark(self, link):
        return self.ns.ApproveItemIntoVirtualLoadout(link, self.profile, None)

    def marked(self):
        lua = self.lua
        return {int(k): str(lua.eval(f'StatVerdictDB.specSnapshots.bySpecID["200"].marked["{k}"]')) for k in (11, 12)
                if lua.eval(f'StatVerdictDB.specSnapshots.bySpecID["200"].marked["{k}"]')}

    def test_two_rings_marked_one_after_the_other_both_stay(self) -> None:
        self.mark(GORE)
        self.mark(PHOENIX)
        marked = self.marked()
        self.assertEqual({11, 12}, set(marked))
        self.assertIn("item:301", marked[11])
        self.assertIn("item:302", marked[12])

    def test_a_third_ring_replaces_the_one_the_comparison_names(self) -> None:
        self.mark(GORE)
        self.mark(PHOENIX)
        self.mark(PREY)
        marked = self.marked()
        self.assertEqual({11, 12}, set(marked))  # still two slots; the new one took slot 11 (the comparison's choice)
        self.assertIn("item:303", marked[11])


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class ReturnToBagSlotTests(unittest.TestCase):
    """A piece that is replaced goes back to the bag slot the new piece came from, not to the first free slot."""

    def setUp(self):
        self.lua = new_runtime()
        self.lua.execute(SETUP)
        self.ns = self.lua.eval("{}")
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        self.lua.execute("""
        BAGSIZE = 10
        bag = {}
        cursor = nil
        GUIDOF = {}
        C_Container.GetContainerNumSlots = function(b) if b == 0 then return BAGSIZE end return 0 end
        C_Container.GetContainerItemLink = function(b, s) if b == 0 then return bag[s] end return nil end
        C_Container.PickupContainerItem = function(b, s)
            if b ~= 0 then return end
            if cursor == nil then cursor = bag[s]; bag[s] = nil else bag[s] = cursor; cursor = nil end
        end
        CursorHasItem = function() return cursor ~= nil end
        ClearCursor = function() if cursor then for i = 1, BAGSIZE do if not bag[i] then bag[i] = cursor; cursor = nil; return end end end end
        """)
        self.ns.GetBagItemGUID = self.lua.eval("function(b, s) local l = bag[s]; return l and GUIDOF[l] or nil end")
        self.lua.execute('GUIDOF["|Hitem:2h::|h[Two-hander]|h"] = "Item-2H"; GUIDOF["|Hitem:ring::|h[Ring]|h"] = "Item-RING"')

    def slots(self):
        return {i: str(self.lua.eval(f"bag[{i}]")) for i in range(1, 11) if self.lua.eval(f"bag[{i}]")}

    def test_the_replaced_piece_goes_back_to_the_slot_the_new_one_came_from(self) -> None:
        # the new piece left slot 3; the game put the replaced two-hander in the first free slot, 1
        self.lua.execute('bag[1] = "|Hitem:2h::|h[Two-hander]|h"; bag[5] = "|Hitem:other::|h[Other]|h"')
        self.ns.NoteBagOrigin("Item-2H", 0, 3)
        self.assertEqual(1, self.ns.ReturnReplacedPiecesToBagSlots())
        self.assertEqual({3: "|Hitem:2h::|h[Two-hander]|h", 5: "|Hitem:other::|h[Other]|h"}, self.slots())
        self.assertFalse(self.lua.eval("CursorHasItem()"))

    def test_a_piece_already_home_is_left_alone(self) -> None:
        self.lua.execute('bag[3] = "|Hitem:2h::|h[Two-hander]|h"')
        self.ns.NoteBagOrigin("Item-2H", 0, 3)
        self.assertEqual(0, self.ns.ReturnReplacedPiecesToBagSlots())
        self.assertEqual({3: "|Hitem:2h::|h[Two-hander]|h"}, self.slots())

    def test_a_place_that_another_piece_took_is_left_alone(self) -> None:
        self.lua.execute('bag[1] = "|Hitem:2h::|h[Two-hander]|h"; bag[3] = "|Hitem:other::|h[Other]|h"')
        self.ns.NoteBagOrigin("Item-2H", 0, 3)
        self.assertEqual(0, self.ns.ReturnReplacedPiecesToBagSlots())
        self.assertEqual({1: "|Hitem:2h::|h[Two-hander]|h", 3: "|Hitem:other::|h[Other]|h"}, self.slots())

    def test_a_piece_that_is_not_in_the_bags_yet_waits_and_is_moved_when_it_arrives(self) -> None:
        self.ns.NoteBagOrigin("Item-2H", 0, 3)
        self.assertEqual(0, self.ns.ReturnReplacedPiecesToBagSlots())   # still on the cursor / in the air
        self.lua.execute('bag[1] = "|Hitem:2h::|h[Two-hander]|h"')
        self.assertEqual(1, self.ns.ReturnReplacedPiecesToBagSlots())
        self.assertEqual({3: "|Hitem:2h::|h[Two-hander]|h"}, self.slots())

    def test_nothing_happens_while_the_cursor_holds_something_or_in_combat(self) -> None:
        self.lua.execute('bag[1] = "|Hitem:2h::|h[Two-hander]|h"; cursor = "|Hitem:x::|h[X]|h"')
        self.ns.NoteBagOrigin("Item-2H", 0, 3)
        self.assertEqual(0, self.ns.ReturnReplacedPiecesToBagSlots())
        self.lua.execute("cursor = nil; InCombatLockdown = function() return true end")
        self.assertEqual(0, self.ns.ReturnReplacedPiecesToBagSlots())
        self.lua.execute("InCombatLockdown = function() return false end")
        self.assertEqual(1, self.ns.ReturnReplacedPiecesToBagSlots())   # the wish was kept
        self.assertEqual({3: "|Hitem:2h::|h[Two-hander]|h"}, self.slots())

    def test_a_two_hander_sends_the_off_hand_piece_to_its_own_home(self) -> None:
        # The axe was put on from bag slot 6 (that is its home); later a two-hander from slot 2 goes on: the sword it replaces
        # goes back to slot 2, and the axe, which the game takes off as a side effect, goes back to slot 6.
        lua = self.lua
        lua.execute("""
        WORN = {}
        ItemLocation = { CreateFromEquipmentSlot = function(_, slot) return { slot = slot } end }
        C_Item.GetItemGUID = function(location) return location.slot and WORN[location.slot] or nil end
        """)
        self.ns.GetItemEquipLocation = lua.eval("function(link) if string.find(link, 'item:2h:') then return 'INVTYPE_2HWEAPON' end return 'INVTYPE_WEAPON' end")
        lua.execute('GUIDOF["|Hitem:sword::|h[Sword]|h"] = "Item-SWORD"; GUIDOF["|Hitem:axe::|h[Axe]|h"] = "Item-AXE"')
        self.ns.NoteEquipFromBag("Item-AXE", 0, 6, 17, "|Hitem:axe::|h[Axe]|h")          # the axe goes on from slot 6
        lua.execute('WORN[16] = "Item-SWORD"; WORN[17] = "Item-AXE"')
        self.ns.NoteEquipFromBag("Item-2H", 0, 2, 16, "|Hitem:2h::|h[Two-hander]|h")      # the two-hander goes on from slot 2
        lua.execute('WORN[16] = "Item-2H"; WORN[17] = nil')
        lua.execute('bag[1] = "|Hitem:sword::|h[Sword]|h"; bag[3] = "|Hitem:axe::|h[Axe]|h"')   # the game put both in the first free slots
        self.assertEqual(2, self.ns.ReturnReplacedPiecesToBagSlots())
        self.assertEqual({2: "|Hitem:sword::|h[Sword]|h", 6: "|Hitem:axe::|h[Axe]|h"}, self.slots())

    def test_a_one_hander_does_not_send_the_off_hand_piece_anywhere(self) -> None:
        lua = self.lua
        lua.execute("""
        WORN = { [16] = "Item-SWORD", [17] = "Item-AXE" }
        ItemLocation = { CreateFromEquipmentSlot = function(_, slot) return { slot = slot } end }
        C_Item.GetItemGUID = function(location) return location.slot and WORN[location.slot] or nil end
        """)
        self.ns.GetItemEquipLocation = lua.eval("function() return 'INVTYPE_WEAPON' end")
        self.ns.NoteEquipFromBag("Item-AXE", 0, 6, 17, "|Hitem:axe::|h[Axe]|h")
        lua.execute('WORN[17] = "Item-AXE"; bag[3] = "|Hitem:other::|h[Other]|h"')
        self.assertEqual(0, self.ns.ReturnReplacedPiecesToBagSlots())

    def test_an_old_wish_is_forgotten(self) -> None:
        self.lua.execute('bag[1] = "|Hitem:2h::|h[Two-hander]|h"')
        self.ns.NoteBagOrigin("Item-2H", 0, 3)
        self.lua.execute("clock = clock + 60")
        self.assertEqual(0, self.ns.ReturnReplacedPiecesToBagSlots())
        self.assertEqual({1: "|Hitem:2h::|h[Two-hander]|h"}, self.slots())


if __name__ == "__main__":
    unittest.main()
