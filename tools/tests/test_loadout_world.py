"""End-to-end loadout scenarios on the simulated game world (tools/tests/world_sim.py): the real marking, putting-on and bag
marker code, driven the way a player drives it."""
import unittest

from tools.tests.test_addon_lua import LuaRuntime
from tools.tests.world_sim import World

MS, OS = 251, 250                  # Frost (played first), Blood (the Off Spec)
MASK, NECK_MS, NECK_OS = 100, 101, 102
RADIANT, COIL, PREY, SIGNET = 256971, 279009, 275528, 276035
ITEMS = {
    MASK: ("head", 5, 5), NECK_MS: ("neck", 9, 2), NECK_OS: ("neck", 2, 9),
    RADIANT: ("ring", 8, 1), COIL: ("ring", 10, 10), PREY: ("ring", 1, 8), SIGNET: ("ring", 3, 3),
}


def pairs_text(world, spec):
    return {s: world.marked_guid(spec, s) for s in (1, 2, 11, 12)}


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class OwnersCaseTests(unittest.TestCase):
    """The state found in the owner's saved file: the Off Spec ring slot marked with a piece that is worn in the other slot."""

    def setUp(self):
        w = self.w = World(ITEMS, played=MS)
        self.g_mask = w.wear(1, MASK)
        self.g_radiant = w.wear(11, RADIANT)
        self.g_coil = w.wear(12, COIL)
        self.g_prey = w.bag(PREY)
        w.snapshot(MS, equipment={1: MASK, 11: RADIANT, 12: COIL}, marked={1: MASK, 11: RADIANT, 12: COIL},
                   markedGUID={1: self.g_mask, 11: self.g_radiant, 12: self.g_coil})
        w.snapshot(OS, equipment={1: MASK, 11: PREY, 12: COIL}, marked={1: MASK, 11: COIL, 12: COIL},
                   markedGUID={1: self.g_mask, 11: self.g_coil, 12: self.g_coil}, manualSlots={11: True})

    def test_the_ring_that_belongs_to_the_off_spec_loadout_shows_OS_while_playing_the_main_spec(self):
        self.w.login()
        self.w.settle()
        self.assertIn("off_spec", self.w.indicator(1))
        self.assertEqual([], self.w.errors())


def clean_world(played=MS):
    """Two rings worn, a neck worn, a spare ring and a spare neck in the bags; no saved loadouts yet."""
    w = World(ITEMS, played=played)
    g = {}
    g["mask"] = w.wear(1, MASK)
    g["neck"] = w.wear(2, NECK_MS)
    g["radiant"] = w.wear(11, RADIANT)
    g["coil"] = w.wear(12, COIL)
    g["prey"] = w.bag(PREY)
    g["neckos"] = w.bag(NECK_OS)
    return w, g


def slot_of(world, guid):
    for slot, (_item, g) in world.worn_ids().items():
        if g == guid:
            return slot
    return None


def bag_slot_of(world, guid):
    for slot, _item, g in world.bag_ids():
        if g == guid:
            return slot
    return None


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class SpecSwitchTests(unittest.TestCase):
    def test_first_login_marks_what_is_worn_for_the_played_spec_only(self):
        w, g = clean_world()
        w.login(); w.settle()
        self.assertEqual(g["radiant"], w.marked_guid(MS, 11))
        self.assertEqual(g["coil"], w.marked_guid(MS, 12))
        self.assertEqual(g["neck"], w.marked_guid(MS, 2))
        self.assertIsNone(w.marked_guid(OS, 11))   # the other build is not touched by an update
        self.assertEqual([], w.errors())

    def test_a_piece_marked_for_the_off_spec_is_put_on_at_respec_and_the_main_piece_goes_to_the_bags(self):
        w, g = clean_world()
        w.login(); w.settle()
        # The player marks the spare ring and neck for the Off Spec (Alt-click on the bag pieces).
        profile = w.lua.eval("{ specID = 250, specName = 'Spec250' }")
        self.assertTrue(w.ns.ApproveItemIntoVirtualLoadout(w.link(PREY), profile, 11, g["prey"]))
        self.assertTrue(w.ns.ApproveItemIntoVirtualLoadout(w.link(NECK_OS), profile, 2, g["neckos"]))
        w.settle()
        w.change_spec(OS)
        w.advance(6)
        self.assertEqual(11, slot_of(w, g["prey"]), "the Off Spec ring is put on in the slot of the weaker ring")
        self.assertEqual(2, slot_of(w, g["neckos"]))
        self.assertIsNotNone(bag_slot_of(w, g["radiant"]))
        self.assertIsNotNone(bag_slot_of(w, g["neck"]))
        w.settle()
        # Back to the main spec: its pieces return.
        w.change_spec(MS)
        w.advance(6)
        self.assertEqual(11, slot_of(w, g["radiant"]))
        self.assertEqual(2, slot_of(w, g["neck"]))
        w.settle()
        self.assertEqual([], w.errors())

    def test_many_round_trips_change_nothing(self):
        w, g = clean_world()
        w.login(); w.settle()
        profile = w.lua.eval("{ specID = 250, specName = 'Spec250' }")
        w.ns.ApproveItemIntoVirtualLoadout(w.link(PREY), profile, 11, g["prey"])
        w.ns.ApproveItemIntoVirtualLoadout(w.link(NECK_OS), profile, 2, g["neckos"])
        w.change_spec(OS); w.settle()
        w.change_spec(MS); w.settle()
        reference = (w.dump(), sorted(w.worn_ids().items()), sorted((i, g_) for _s, i, g_ in w.bag_ids()))
        for _ in range(6):
            w.change_spec(OS); w.settle()
            w.change_spec(MS); w.settle()
        again = (w.dump(), sorted(w.worn_ids().items()), sorted((i, g_) for _s, i, g_ in w.bag_ids()))
        self.assertEqual(reference[0], again[0])
        self.assertEqual(reference[1], again[1])
        self.assertEqual(reference[2], again[2])
        self.assertEqual([], w.errors())

    def test_the_off_spec_piece_in_the_bags_shows_OS_and_the_main_one_shows_MS_after_respec(self):
        w, g = clean_world()
        w.login(); w.settle()
        profile = w.lua.eval("{ specID = 250, specName = 'Spec250' }")
        w.ns.ApproveItemIntoVirtualLoadout(w.link(PREY), profile, 11, g["prey"])
        w.settle()
        self.assertIn("off_spec", w.indicator(bag_slot_of(w, g["prey"])))
        w.change_spec(OS); w.settle()
        self.assertIn("main_spec", w.indicator(bag_slot_of(w, g["radiant"])))

    def test_a_piece_worn_by_hand_in_the_off_spec_is_marked_for_it_and_stays_known_in_the_bags(self):
        w, g = clean_world()
        w.login(); w.settle()
        w.change_spec(OS); w.settle()                  # nothing marked for the Off Spec yet: gear stays as it is
        w.put_on(bag_slot_of(w, g["prey"]), 11); w.settle()
        self.assertEqual(g["prey"], w.marked_guid(OS, 11))
        w.take_off(11); w.settle()
        # It was taken off: the Off Spec mark of the slot leaves with it, but the Main Spec one is untouched.
        self.assertEqual(g["radiant"], w.marked_guid(MS, 11))
        self.assertEqual([], w.errors())

    def test_a_quick_switch_back_does_not_mark_the_old_gear_for_the_new_spec(self):
        w, g = clean_world()
        w.login(); w.settle()
        w.change_spec(OS)
        w.advance(2)                                   # inside the quiet time
        w.change_spec(MS)
        w.settle()
        self.assertIsNone(w.marked_guid(OS, 11))
        self.assertEqual(g["radiant"], w.marked_guid(MS, 11))

    def test_nothing_changes_in_combat(self):
        w, g = clean_world()
        w.login(); w.settle()
        before = w.dump()
        w.set_combat(True)
        w.put_on(bag_slot_of(w, g["prey"]), 11)
        w.settle()
        self.assertEqual(before, w.dump())
        self.assertEqual([], w.errors())

    def test_two_copies_of_the_same_ring_are_told_apart_by_serial_number(self):
        w, g = clean_world()
        copy = w.bag(PREY)                             # a second Preyhunter's Ring
        w.login(); w.settle()
        profile = w.lua.eval("{ specID = 250, specName = 'Spec250' }")
        w.ns.ApproveItemIntoVirtualLoadout(w.link(PREY), profile, 11, copy)
        w.settle()
        self.assertIn("off_spec", w.indicator(bag_slot_of(w, copy)))
        self.assertNotIn("off_spec", w.indicator(bag_slot_of(w, g["prey"])))
        w.change_spec(OS); w.advance(6)
        self.assertEqual(11, slot_of(w, copy), "the marked copy is the one that is put on")


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class FoundByRandomPlayTests(unittest.TestCase):
    """Situations the random play found, kept as exact scenarios."""

    def test_a_marked_piece_is_recognised_even_when_its_slot_is_empty(self):
        w = World(ITEMS, played=OS)
        g = w.bag(RADIANT)
        w.snapshot(MS, equipment={}, marked={11: RADIANT}, markedGUID={11: g})
        w.snapshot(OS, equipment={}, marked={}, markedGUID={}, seeded=True)
        w.settle()
        self.assertIn("main_spec", w.indicator(1))

    def test_a_piece_that_moved_to_the_other_ring_slot_takes_the_mark_and_the_slot_it_left_is_marked_too(self):
        # Off Spec: ring slot 11 was marked by hand with PREY (the lock remembers the ring worn then). While the Main Spec was
        # played, PREY was put on in slot 12. At the respec both slots are looked at in one go.
        w = World(ITEMS, played=MS)
        g_other = w.wear(11, RADIANT)
        g_prey = w.wear(12, PREY)
        w.snapshot(MS, equipment={11: RADIANT, 12: PREY}, marked={11: RADIANT, 12: PREY}, markedGUID={11: g_other, 12: g_prey})
        w.snapshot(OS, equipment={11: PREY}, marked={11: PREY}, markedGUID={11: g_prey}, manualSlots={11: g_other})
        w.login(); w.settle()
        w.change_spec(OS); w.settle()
        self.assertEqual(g_prey, w.marked_guid(OS, 12))
        self.assertEqual(g_other, w.marked_guid(OS, 11), "the ring worn in slot 11 is the Off Spec mark of that slot now")

    def test_taking_a_hand_mark_away_for_the_played_spec_marks_what_is_worn_without_another_event(self):
        w, g = clean_world(played=OS)
        w.login(); w.settle()
        profile = w.lua.eval("{ specID = 250, specName = 'Spec250' }")
        w.ns.ApproveItemIntoVirtualLoadout(w.link(NECK_OS), profile, 2, g["neckos"])   # a hand mark waits in the bags
        w.settle()
        self.assertEqual(g["neckos"], w.marked_guid(OS, 2))
        self.assertTrue(w.ns.RemoveItemFromVirtualLoadout(w.link(NECK_OS), profile, g["neckos"]))
        w.settle()                                                                     # no gear event at all
        self.assertEqual(g["neck"], w.marked_guid(OS, 2))

    def test_the_end_of_a_fight_catches_up_with_a_respec_that_fell_in_combat(self):
        w, g = clean_world()
        w.login(); w.settle()
        w.change_spec(OS)
        w.advance(5)
        w.set_combat(True)
        w.advance(6)                                    # the marking time passes inside the fight
        w.set_combat(False)
        w.settle()
        self.assertEqual(g["radiant"], w.marked_guid(OS, 11))
