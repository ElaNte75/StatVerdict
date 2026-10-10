"""Random play on the simulated world: whatever the player does, the loadouts must keep their promises."""
import random
import unittest

from tools.tests.test_addon_lua import LuaRuntime
from tools.tests.test_loadout_world import ITEMS, MS, OS, MASK, NECK_MS, NECK_OS, RADIANT, COIL, PREY, SIGNET
from tools.tests.world_sim import World

SLOTS_OF = {"head": [1], "neck": [2], "ring": [11, 12]}
KIND_OF = {i: v[0] for i, v in ITEMS.items()}


def start_world(rng):
    w = World(ITEMS, played=rng.choice([MS, OS]))
    spare = [MASK, NECK_MS, NECK_OS, RADIANT, COIL, PREY, SIGNET, PREY, NECK_OS]
    rng.shuffle(spare)
    placed = {1: None, 2: None, 11: None, 12: None}
    for item in spare:
        kind = KIND_OF[item]
        free = [s for s in SLOTS_OF[kind] if placed[s] is None]
        if free and rng.random() < 0.7:
            placed[free[0]] = item
            w.wear(free[0], item)
        else:
            w.bag(item)
    return w


def world_pieces(w):
    return sorted([(i, g) for _s, (i, g) in w.worn_ids().items()] + [(i, g) for _s, i, g in w.bag_ids()])


def act(w, rng, log):
    kind = rng.choice(["spec", "spec", "put_on", "put_on", "take_off", "mark", "unmark", "wait", "combat"])
    played = int(w.lua.eval("SPEC"))
    if kind == "spec":
        target = OS if played == MS else MS
        log.append(f"change_spec({target})")
        w.change_spec(target)
        w.advance(rng.choice([1, 3, 6, 8, 20]))
    elif kind == "put_on":
        bag = w.bag_ids()
        if bag:
            bs, item, _g = rng.choice(bag)
            slot = rng.choice(SLOTS_OF[KIND_OF[item]])
            log.append(f"put_on(bag {bs} item {item} -> slot {slot})")
            w.put_on(bs, slot)
            w.advance(rng.choice([0.5, 3, 9]))
    elif kind == "take_off":
        worn = w.worn_ids()
        if worn:
            slot = rng.choice(list(worn))
            log.append(f"take_off({slot})")
            w.take_off(slot)
            w.advance(rng.choice([0.5, 3, 9]))
    elif kind in ("mark", "unmark"):
        # Alt-click on a bag piece is a toggle: a piece already saved in that loadout is taken out, else it is saved.
        bag = w.bag_ids()
        if bag:
            bs, item, g = rng.choice(bag)
            slot = rng.choice(SLOTS_OF[KIND_OF[item]])
            spec = OS if played == MS else MS
            if rng.random() < 0.25:
                spec = played
            profile = w.lua.eval(f"{{ specID = {spec}, specName = 'Spec{spec}' }}")
            if w.ns.IsPieceMarkedInLoadout(profile, w.link(item), g):
                log.append(f"alt-click removes item {item} guid {g} from {spec}")
                w.ns.RemoveItemFromVirtualLoadout(w.link(item), profile, g)
            else:
                log.append(f"alt-click saves item {item} guid {g} slot {slot} for {spec}")
                w.ns.ApproveItemIntoVirtualLoadout(w.link(item), profile, slot, g)
            w.advance(1)
    elif kind == "combat":
        log.append("combat on, put_on attempt, combat off")
        w.set_combat(True)
        bag = w.bag_ids()
        if bag:
            w.put_on(bag[0][0], SLOTS_OF[KIND_OF[bag[0][1]]][0])
        w.advance(5)
        w.set_combat(False)
    else:
        t = rng.choice([1, 5, 15])
        log.append(f"wait({t})")
        w.advance(t)


def check(w, before_pieces, log, tag):
    problems = []
    w.advance(30)   # let everything settle first
    if w.errors():
        problems.append(f"Lua errors: {w.errors()[:2]}")
    if world_pieces(w) != before_pieces:
        problems.append("a piece was lost or duplicated")
    # I1: one piece is never marked in two slots of one loadout
    for spec in (MS, OS):
        seen = {}
        for slot in (1, 2, 11, 12):
            g = w.marked_guid(spec, slot)
            if g:
                if g in seen:
                    problems.append(f"spec {spec}: piece {g} marked in slots {seen[g]} and {slot}")
                seen[g] = slot
    # I3: nothing moves by itself
    w.advance(30)
    snapshot = (w.dump(), sorted(w.worn_ids().items()))
    w.advance(30)
    if (w.dump(), sorted(w.worn_ids().items())) != snapshot:
        problems.append("the state changed by itself after settling")
    # I4: the played spec marks what it wears (a hand mark may hold a slot)
    played = int(w.lua.eval("SPEC"))
    for slot, (_item, g) in w.worn_ids().items():
        locked = w.lua.eval(f'(StatVerdictDB.specSnapshots.bySpecID["{played}"] or {{}}).manualSlots and StatVerdictDB.specSnapshots.bySpecID["{played}"].manualSlots["{slot}"]')
        mg = w.marked_guid(played, slot)
        if not locked and mg != g:
            problems.append(f"played spec {played}: slot {slot} wears {g} but the mark is {mg}")
    # I5: a bag piece that is marked in a loadout shows that build's letter
    for bs, item, g in w.bag_ids():
        in_specs = {s for s in (MS, OS) if g in [w.marked_guid(s, slot) for slot in (1, 2, 11, 12)]}
        shown = w.indicator(bs)
        want = {MS: "main_spec", OS: "off_spec"}
        if in_specs == {MS, OS}:
            ok = "both_specs" in shown
        elif in_specs:
            ok = want[next(iter(in_specs))] in shown or "both_specs" in shown
        else:
            ok = True
        if not ok:
            problems.append(f"bag piece {item} {g} is marked for {sorted(in_specs)} but shows {shown}")
    if problems:
        return f"[{tag}] " + "; ".join(problems) + "\n  " + "\n  ".join(log[-14:])
    return None


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class RandomPlayTests(unittest.TestCase):
    SEEDS = 400
    STEPS = 22

    def test_random_play_keeps_the_promises(self):
        failures = []
        for seed in range(self.SEEDS):
            rng = random.Random(seed)
            w = start_world(rng)
            w.login(); w.advance(30)
            pieces = world_pieces(w)
            log = [f"seed {seed}"]
            for step in range(self.STEPS):
                act(w, rng, log)
                if step % 7 == 6:
                    msg = check(w, pieces, log, f"seed {seed} step {step}")
                    if msg:
                        failures.append(msg)
                        break
            else:
                msg = check(w, pieces, log, f"seed {seed} end")
                if msg:
                    failures.append(msg)
        self.assertEqual([], failures[:5], f"{len(failures)} of {self.SEEDS} runs broke a promise")


def worn_guids(w):
    return {g for _s, (_i, g) in w.worn_ids().items()}


def marked_set(w, spec):
    return {w.marked_guid(spec, s) for s in (1, 2, 11, 12)} - {None}


def where_is(w, guid):
    for s, (_i, g) in w.worn_ids().items():
        if g == guid:
            return "worn"
    for _bs, _i, g in w.bag_ids():
        if g == guid:
            return "bag"
    return None


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class RespecPutsOnEverythingMarkedTests(unittest.TestCase):
    """After a spec change has settled, every piece marked for that spec is worn."""

    def test_every_marked_piece_is_worn_after_a_respec(self):
        failures = []
        for seed in range(150):
            rng = random.Random(1000 + seed)
            w = start_world(rng)
            w.login(); w.advance(30)
            log = [f"seed {seed}"]
            for step in range(14):
                act(w, rng, log)
            w.set_combat(False)
            w.advance(30)
            for _ in range(4):
                target = OS if int(w.lua.eval("SPEC")) == MS else MS
                log.append(f"respec to {target}")
                w.change_spec(target)
                w.advance(30)
                wanted = marked_set(w, target)
                missing = [g for g in wanted if where_is(w, g) == "bag"]
                if missing:
                    failures.append(f"seed {seed}: after respec to {target} these marked pieces stayed in the bags: {missing}\n  " + "\n  ".join(log[-10:]))
                    break
        self.assertEqual([], failures[:4], f"{len(failures)} runs")


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class UpgradeKeepsMarksTests(unittest.TestCase):
    """An upgrade can give a piece a new serial number: its marks follow it, in both builds."""

    def test_marks_follow_an_upgraded_piece(self):
        failures = []
        for seed in range(150):
            rng = random.Random(5000 + seed)
            w = start_world(rng)
            w.login(); w.advance(30)
            profile_os = w.lua.eval("{ specID = 250, specName = 'Spec250' }")
            profile_ms = w.lua.eval("{ specID = 251, specName = 'Spec251' }")
            for bs, item, g in w.bag_ids():
                for spec, profile in ((OS, profile_os), (MS, profile_ms)):
                    if rng.random() < 0.4 and not w.ns.IsPieceMarkedInLoadout(profile, w.link(item), g):
                        w.ns.ApproveItemIntoVirtualLoadout(w.link(item), profile, rng.choice(SLOTS_OF[KIND_OF[item]]), g)
            w.advance(10)
            # pick one piece that is marked somewhere and upgrade it (new level, new serial number)
            candidates = []
            for bs, item, g in w.bag_ids():
                specs = [s for s in (MS, OS) if g in marked_set(w, s)]
                if specs and [i2 for i2, _g in [(i3, g3) for _s3, (i3, g3) in w.worn_ids().items()]] .count(item) + [i2 for _b, i2, _g in w.bag_ids()].count(item) == 1:
                    candidates.append((bs, item, g, specs))
            if not candidates:
                continue
            bs, item, g, specs = rng.choice(candidates)
            new_guid = w.new_guid()
            w.lua.execute(f'bagItems[{bs}] = {{ link = "{w.link(item, 5)}", guid = "{new_guid}" }}')
            w.lua.execute("pendingEvents = true")
            w.advance(30)
            for s in specs:
                if new_guid not in marked_set(w, s):
                    failures.append(f"seed {seed}: item {item} was marked for {s}, after the upgrade its new serial number is not")
        self.assertEqual([], failures[:4], f"{len(failures)} cases")
