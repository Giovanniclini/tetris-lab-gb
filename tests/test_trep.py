#!/usr/bin/env python3
"""The TREP manifest must describe the ROM that actually exists.

    .venv/bin/python tests/test_trep.py

TREP is Tolstoj's ROM editor. It reads the built ROM plus a metadata file this
build generates, and shows the tilesets and background maps as editable
pictures. See docs/decisions/0012.

Layouts carry no `.end` label, so TREP reads width x height bytes from the
symbol and trusts the manifest for the size. A wrong figure does not fail - it
shows a plausible wrong screen. So every declared dimension is checked here,
where being wrong is loud: against the .bin it was assembled from where there
is one, and against the span to the next symbol where there is not.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MANIFEST = ROOT / "tetrislab.trep-source.json"
DATA_DIRS = (ROOT / "src" / "original" / "data", ROOT / "src" / "lab" / "data")
SYM = ROOT / "build" / "tetrislab.sym"
GENERATED = ROOT / "build" / "tetrislab.trep.json"

BYTES_PER_TILE = {1: 8, 2: 16}


def manifest():
    return json.loads(MANIFEST.read_text())


def symbols():
    out = {}
    for line in SYM.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and ":" in parts[0]:
            bank, addr = parts[0].split(":")
            out.setdefault(parts[1], (int(bank, 16), int(addr, 16)))
    return out


def test_every_declared_dimension_matches_the_data():
    files = {p.name.lower(): p.stat().st_size
             for d in DATA_DIRS for p in d.glob("*.bin")}
    for entry in manifest()["backgroundMaps"]:
        if "filename" not in entry:
            continue
        name = entry["filename"].lower()
        assert name in files, f"{entry['symbol']}: no data file called {name}"
        visible = entry["width"] * entry["height"]
        declared = entry.get("fileSize", visible)
        assert declared >= visible, f"{entry['symbol']}: fileSize is smaller than the visible map"
        assert declared == files[name], (
            f"{entry['symbol']}: manifest says {declared} file bytes, "
            f"the file is {files[name]}"
        )


def next_symbol_address(have, symbol):
    """Where the symbol after this one starts, in the same bank."""
    bank, addr = have[symbol]
    later = [a for b, a in have.values() if b == bank and a > addr]
    return min(later) if later else None


def test_maps_without_a_data_file_end_where_the_next_symbol_begins():
    """Layouts assembled inline have no .bin to be checked against, and those
    are exactly the ones a wrong figure hides in - nothing else reads them.
    The span to the next symbol is the only independent witness to the size,
    so it is the one used. It caught Pause declared 10x3 when it is 8x10.
    """
    have = symbols()
    for entry in manifest()["backgroundMaps"]:
        if "filename" in entry:
            continue
        declared = entry["width"] * entry["height"]
        end = next_symbol_address(have, entry["symbol"])
        assert end is not None, (
            f"{entry['symbol']}: no symbol follows it, so its size cannot be checked"
        )
        span = end - have[entry["symbol"]][1]
        assert declared == span, (
            f"{entry['symbol']}: manifest says {entry['width']}x{entry['height']}"
            f" = {declared} bytes, the symbol spans {span}"
        )


def test_every_symbol_the_manifest_names_exists():
    """A rename in the disassembly would otherwise break TREP silently."""
    have = symbols()
    for key in ("tileRegions", "backgroundMaps"):
        for entry in manifest()[key]:
            for field in ("symbol", "endSymbol"):
                sym = entry.get(field)
                assert not sym or sym in have, f"{sym} is not in the symbol file"


def test_tile_regions_are_a_whole_number_of_tiles():
    have = symbols()
    for entry in manifest()["tileRegions"]:
        if "endSymbol" not in entry:
            assert entry.get("tileCount", 0) > 0
            continue
        span = have[entry["endSymbol"]][1] - have[entry["symbol"]][1]
        per = BYTES_PER_TILE[entry["bitsPerPixel"]]
        assert span > 0 and span % per == 0, (
            f"{entry['symbol']}: {span} bytes is not a whole number of "
            f"{entry['bitsPerPixel']}bpp tiles"
        )


def test_the_build_exports_every_label():
    """TREP reads the .sym, and most of the labels it wants are declared with a
    single colon - local to their object file. They only reach the .sym because
    rgbasm runs with -E. Removing that flag breaks TREP with no error at all,
    so the flag is load-bearing and this says so."""
    assert '"-E"' in (ROOT / "build.py").read_text(), (
        "build.py no longer assembles with -E; single-colon labels will vanish "
        "from the .sym and TREP will see nothing"
    )


def test_every_map_resolves_to_its_own_data_in_the_rom():
    """The end-to-end check: manifest -> generator -> resolved offset -> ROM.

    Reads each map's bytes out of the built ROM at the address the generator
    worked out, and compares them with the source .bin they were assembled
    from. If those agree, TREP is looking at the screen the manifest claims.
    This is as close to testing TREP as we can get without running it.
    """
    meta = json.loads(GENERATED.read_text())
    rom = (ROOT / "build" / "tetrislab.gb").read_bytes()
    files = {p.name.lower(): p for d in DATA_DIRS for p in d.glob("*.bin")}
    for entry in meta["backgroundMaps"]:
        if "filename" not in entry:
            continue
        name = entry["filename"].lower()
        visible = entry["width"] * entry["height"]
        want = files[name].read_bytes()[: entry.get("fileSize", visible)]
        start = int(entry["start"], 16)
        got = rom[start : start + len(want)]
        assert got == want, (
            f"{entry['symbol']}: the ROM at ${start:05X} is not this layout's data"
        )


def test_the_build_generates_the_metadata():
    assert GENERATED.exists(), "build/tetrislab.trep.json was not generated"
    data = json.loads(GENERATED.read_text())
    assert data["format"] == "trep-metadata"
    assert len(data["backgroundMaps"]) == len(manifest()["backgroundMaps"])
    for entry in data["backgroundMaps"]:
        assert "start" in entry, f"{entry['symbol']} has no resolved address"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failures = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    raise SystemExit(1 if failures else 0)
