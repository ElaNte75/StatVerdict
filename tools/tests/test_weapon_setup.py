"""Weapons: the guide decides how a spec holds them (two weapons or a two-hander), and a dual wield build that wears a
two-hander compares the best two one-handers of the bags with it. Real scoring, real generated data."""
from __future__ import annotations

import unittest

from tools import addon_harness as verdict
from tools.tests.test_addon_lua import LuaRuntime
from tools.tests.test_scoring_mechanism import STATES, base_item

FROST = dict(classFile="DEATHKNIGHT", className="Death Knight", specKey="DEATHKNIGHT_FROST", specID=251,
             role="DAMAGER", heroTalentName="Rider of the Apocalypse")
BLOOD = dict(classFile="DEATHKNIGHT", className="Death Knight", specKey="DEATHKNIGHT_BLOOD", specID=250,
             role="TANK", heroTalentName="Deathbringer")
STATS_2H = {"strength": 1400, "crit_rating": 300, "haste_rating": 200}
STATS_1H = {"strength": 800, "crit_rating": 170, "haste_rating": 130}


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WeaponSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = verdict.load_addon()
        cls.saved_character = dict(verdict.CHARACTER)

    @classmethod
    def tearDownClass(cls) -> None:
        verdict.CHARACTER.clear()
        verdict.CHARACTER.update(cls.saved_character)

    # --- helpers -----------------------------------------------------------------------------------------------

    def register(self, link, ilvl, equip_loc, stats):
        lua = self.lua
        item = {"name": link, "ilevel": ilvl, **stats}
        lua.globals().ITEMS[link] = lua.table(
            id=int(link.split(":")[1]) if link.split(":")[1].isdigit() else 900000 + abs(hash(link)) % 99999,
            name=link, ilvl=float(ilvl), equipLoc=equip_loc, stats=lua.table_from(verdict.item_stats(item)),
            classID=2, subID=7, subclass="Weapon")

    def start(self, character, worn_main, worn_off=None, bags=()):
        """A death knight with `worn_main` (and `worn_off`) on, `bags` in the bags: the profile and the links."""
        lua, ns = self.lua, self.ns
        verdict.CHARACTER.clear()
        verdict.CHARACTER.update(character)
        lua.execute(f"""UnitClass = function() return "{character['className']}", "{character['classFile']}", 6 end
GetSpecialization = function() return 1 end
GetSpecializationInfo = function() return {character['specID']}, "x", "", 0, "{character['role']}", "STRENGTH" end""")
        verdict.set_character(lua, STATES["mid"], 1600)
        lua.execute(f"""UnitClass = function() return "{character['className']}", "{character['classFile']}", 6 end
GetSpecialization = function() return 1 end
GetSpecializationInfo = function() return {character['specID']}, "x", "", 0, "{character['role']}", "STRENGTH" end""")
        lua.globals().StatVerdictDB = lua.table()
        ns.ProfileRepository.InvalidateProviderViews()
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", "GUIDE")
        equipped = lua.table()
        for gear_slot, (slot_id, _) in verdict.SLOTS.items():
            if slot_id in (16, 17):
                continue
            link = f"item:{gear_slot}:292"
            raw = dict(base_item(gear_slot))
            raw["ilevel"] = 292
            verdict.register_item(lua, link, 1, raw, gear_slot)
            equipped[slot_id] = link
        equipped[16] = worn_main
        if worn_off:
            equipped[17] = worn_off
        lua.globals().EQUIPPED = equipped
        links = list(bags)
        lua.globals().BAGS = lua.table_from(links)
        lua.execute("""C_Container = C_Container or {}
C_Container.GetContainerNumSlots = function(bag) if bag == 0 then return #BAGS end return 0 end
C_Container.GetContainerItemLink = function(bag, slot) if bag == 0 then return BAGS[slot] end return nil end
UPG = {}; C_Item.GetItemUpgradeInfo = function(l) return UPG[l] end""")
        ns.ClearUpgradeIndicatorDecisionCache()
        return profile

    def register_guide_weapons(self, profile, main_loc, off_loc):
        """The weapons of the profile's Best in Slot list, as the game would know them."""
        for entry in self_slots(profile):
            if entry.slot == "Main Hand":
                self.lua.globals().ITEMS[f"item:{int(entry.item.item_id)}"] = self.lua.table(
                    id=int(entry.item.item_id), name="bis main", ilvl=334.0, equipLoc=main_loc, stats=self.lua.table(),
                    classID=2, subID=7, subclass="Weapon")
            if entry.slot == "Off Hand" and off_loc:
                self.lua.globals().ITEMS[f"item:{int(entry.item.item_id)}"] = self.lua.table(
                    id=int(entry.item.item_id), name="bis off", ilvl=334.0, equipLoc=off_loc, stats=self.lua.table(),
                    classID=2, subID=7, subclass="Weapon")

    def compare(self, link, profile):
        self.ns.ClearUpgradeIndicatorDecisionCache()
        return self.ns.BuildComparison(link, profile)

    # --- the setup the guide plays -----------------------------------------------------------------------------

    def test_a_list_with_two_weapons_is_dual_wield_and_a_list_with_one_is_single(self) -> None:
        frost = self.start(FROST, "item:2h:292")
        self.register_guide_weapons(frost, "INVTYPE_WEAPON", "INVTYPE_WEAPON")
        self.assertEqual("DUAL", self.ns.GetGuideWeaponSetup(frost))
        blood = self.start(BLOOD, "item:2h:292")
        self.register_guide_weapons(blood, "INVTYPE_2HWEAPON", "INVTYPE_2HWEAPON")
        self.assertEqual("SINGLE", self.ns.GetGuideWeaponSetup(blood))   # no weapon in its Off Hand slot

    def test_the_setup_is_unknown_until_the_item_data_is_there(self) -> None:
        self.lua.globals().ITEMS = self.lua.table()   # the game knows no item yet
        frost = self.start(FROST, "item:2h:292")
        self.assertIsNone(self.ns.GetGuideWeaponSetup(frost))

    # --- a two-hander build never takes a one-hander for an empty off hand ---------------------------------------

    def test_blood_does_not_take_a_one_hander_for_its_empty_off_hand(self) -> None:
        self.register("item:2h:292", 292, "INVTYPE_2HWEAPON", STATS_2H)
        self.register("item:axe:292", 292, "INVTYPE_WEAPON", STATS_1H)
        profile = self.start(BLOOD, "item:2h:292", bags=["item:axe:292"])
        self.register_guide_weapons(profile, "INVTYPE_2HWEAPON", None)
        comparison = self.compare("item:axe:292", profile)
        self.assertIsNone(comparison.selected)

    # --- a dual wield build ------------------------------------------------------------------------------------

    def frost_with_two_hander(self, bags):
        for link, level in (("item:sword:292", 292), ("item:axe:285", 285), ("item:old:270", 270)):
            self.register(link, level, "INVTYPE_WEAPON", STATS_1H)
        self.register("item:2h:292", 292, "INVTYPE_2HWEAPON", STATS_2H)
        profile = self.start(FROST, "item:2h:292", bags=bags)
        self.register_guide_weapons(profile, "INVTYPE_WEAPON", "INVTYPE_WEAPON")
        return profile

    def test_two_one_handers_in_the_bags_are_compared_as_a_pair_with_the_worn_two_hander(self) -> None:
        profile = self.frost_with_two_hander(["item:sword:292", "item:axe:285"])
        sword = self.compare("item:sword:292", profile).selected
        axe = self.compare("item:axe:285", profile).selected
        self.assertTrue(sword.isUpgrade and axe.isUpgrade)
        self.assertEqual({16, 17}, {int(sword.slotID), int(axe.slotID)})   # each weapon knows its own hand
        self.assertEqual("item:axe:285", sword.pairPartnerLink)
        self.assertEqual("item:sword:292", axe.pairPartnerLink)
        self.assertEqual("item:2h:292", sword.equippedLink)
        self.assertGreater(sword.deltaScore, 0)
        self.assertEqual(sword.deltaScore, axe.deltaScore)   # one verdict for the pair

    def test_two_weapons_of_slightly_lower_level_are_still_what_the_guide_asks_for(self) -> None:
        # Two one-handers ten item levels under the two-hander and with a little less in stats: the guide plays two
        # weapons, so the pair is recommended anyway.
        for link, level in (("item:low1:282", 282), ("item:low2:282", 282)):
            self.register(link, level, "INVTYPE_WEAPON", {"strength": 740, "crit_rating": 150, "haste_rating": 110})
        self.register("item:2h:292", 292, "INVTYPE_2HWEAPON", STATS_2H)
        profile = self.start(FROST, "item:2h:292", bags=["item:low1:282", "item:low2:282"])
        self.register_guide_weapons(profile, "INVTYPE_WEAPON", "INVTYPE_WEAPON")
        selected = self.compare("item:low1:282", profile).selected
        self.assertTrue(selected.isUpgrade)
        self.assertEqual("item:low2:282", selected.pairPartnerLink)

    def test_two_much_weaker_weapons_do_not_win_just_by_being_two(self) -> None:
        for link in ("item:weak1:292", "item:weak2:292"):
            self.register(link, 292, "INVTYPE_WEAPON", {"strength": 150, "crit_rating": 30, "haste_rating": 20})
        self.register("item:2h:292", 292, "INVTYPE_2HWEAPON", STATS_2H)
        profile = self.start(FROST, "item:2h:292", bags=["item:weak1:292", "item:weak2:292"])
        self.register_guide_weapons(profile, "INVTYPE_WEAPON", "INVTYPE_WEAPON")
        selected = self.compare("item:weak1:292", profile).selected
        self.assertFalse(selected.isUpgrade)

    def test_one_one_hander_alone_has_no_verdict_against_the_two_hander(self) -> None:
        profile = self.frost_with_two_hander(["item:sword:292"])
        self.assertIsNone(self.compare("item:sword:292", profile).selected)

    def test_a_weapon_far_below_the_worn_one_does_not_make_a_pair(self) -> None:
        profile = self.frost_with_two_hander(["item:sword:292", "item:old:270"])   # 270 is under 292 - 10
        self.assertIsNone(self.compare("item:sword:292", profile).selected)
        self.assertIsNone(self.compare("item:old:270", profile).selected)

    def test_only_the_two_weapons_of_the_best_pair_get_the_verdict(self) -> None:
        profile = self.frost_with_two_hander(["item:sword:292", "item:axe:285", "item:old:270"])
        self.register("item:mace:290", 290, "INVTYPE_WEAPON", {"strength": 900, "crit_rating": 190, "haste_rating": 140})
        self.lua.globals().BAGS = self.lua.table_from(["item:sword:292", "item:axe:285", "item:mace:290"])
        self.assertTrue(self.compare("item:sword:292", profile).selected.isUpgrade)
        self.assertTrue(self.compare("item:mace:290", profile).selected.isUpgrade)
        self.assertIsNone(self.compare("item:axe:285", profile).selected)   # the weakest of three: not one of the best two

    def test_a_two_hander_is_never_compared_with_two_worn_one_handers(self) -> None:
        self.register("item:sword:292", 292, "INVTYPE_WEAPON", STATS_1H)
        self.register("item:axe:285", 285, "INVTYPE_WEAPON", STATS_1H)
        self.register("item:big:300", 300, "INVTYPE_2HWEAPON", STATS_2H)
        profile = self.start(FROST, "item:sword:292", "item:axe:285", bags=["item:big:300"])
        self.register_guide_weapons(profile, "INVTYPE_WEAPON", "INVTYPE_WEAPON")
        self.assertIsNone(self.compare("item:big:300", profile).selected)

    def test_a_one_hander_is_still_compared_with_the_worn_one_handers(self) -> None:
        self.register("item:sword:292", 292, "INVTYPE_WEAPON", STATS_1H)
        self.register("item:axe:285", 285, "INVTYPE_WEAPON", STATS_1H)
        self.register("item:new:310", 310, "INVTYPE_WEAPON", {"strength": 900, "crit_rating": 200, "haste_rating": 150})
        profile = self.start(FROST, "item:sword:292", "item:axe:285", bags=["item:new:310"])
        self.register_guide_weapons(profile, "INVTYPE_WEAPON", "INVTYPE_WEAPON")
        selected = self.compare("item:new:310", profile).selected
        self.assertTrue(selected.isUpgrade)
        self.assertIsNone(selected.pairPartnerLink)


def self_slots(profile):
    slots = profile.generatedContext.bis.slots
    return [slots[i] for i in range(1, len(slots) + 1)]


if __name__ == "__main__":
    unittest.main()
