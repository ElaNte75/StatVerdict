import re
from pathlib import Path

paths = {
    "DEV": Path(r"C:\Users\ElaNte\Desktop\Projects\StatVerdict\StatVerdict\Data\Generated\SV_ProfileData.lua"),
    "LIVE": Path(r"D:\Battlenet Games\World of Warcraft\_retail_\Interface\AddOns\StatVerdict\Data\Generated\SV_ProfileData.lua"),
}

for label, path in paths.items():
    if not path.exists():
        print(label, "MISSING")
        continue
    text = path.read_text(encoding="utf-8")
    gen = re.search(r'\["generatedAt"\] = "([^"]+)"', text)
    print(f"=== {label} generatedAt={gen.group(1) if gen else '?'} size={path.stat().st_size}")
    idx = text.find('["DEATHKNIGHT_BLOOD"]')
    chunk = text[idx:idx + 15000]
    # first context bis block slots
    slots = re.findall(r'\["slot"\] = "([^"]+)"', chunk)
    ids = re.findall(r'\["item_id"\] = (\d+)', chunk)
    print(" first slots/ids:", list(zip(slots[:16], ids[:16])))
    avgs = re.findall(r'\["averageItemLevel"\] = ([^\n,]+)', chunk)
    print(" averageItemLevels:", avgs[:6])
    # empty bis?
    empty_bis = len(re.findall(r'\["bis"\] = \{\s*\["label"\] = "[^"]+",\s*\["slots"\] = \{\s*\},', text, re.S))
    print(" approx empty bis blocks:", empty_bis)
    profiles = re.findall(r'^\s+\["([A-Z]+_[A-Z0-9_]+)"\] = \{', text, re.M)
    # filter to top-level-ish: those followed soon by classToken
    print(" profile-like keys count:", len(set(profiles)))
