#!/usr/bin/env python3
"""Build the TetrisGYM-GB ROM.

    python3 build.py               build the Lab ROM       (LAB=1)
    python3 build.py --original    rebuild the stock ROM   (LAB=0)  <- the regression test
    python3 build.py --freespace   also print per-bank free space
    python3 build.py --patch       also emit build/tetrislab.bps for release

Requires only Python 3 and network access on first run; the pinned RGBDS
toolchain is fetched into build/toolchain/. Nothing is installed system-wide.
"""

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tools import gfx, patch, rgbds, trep  # noqa: E402

ROOT = Path(__file__).parent.resolve()
SRC = ROOT / "src" / "original"
BUILD = ROOT / "build"
TREP_SOURCE = ROOT / "tetrislab.trep-source.json"
OBJ = BUILD / "obj"

# Tetris (World) (Rev A), a.k.a. v1.1 - the community standard.
# See docs/architecture.md D2 and docs/community-research.md section 3.5.6.
REFERENCE_SHA1 = "74591cc9501af93873f9a5d3eb12da12c0723bbc"
REFERENCE_MD5 = "982ed5d2b12a0377eb14bcdc4123744e"

# Translation units, in link order. The original disassembly is one big
# address-fixed ROM0 section plus the sound engine in bank 1.
UNITS = [
    ("bank_000", SRC / "code" / "bank_000.s"),
    ("soundEngine", SRC / "code" / "soundEngine.s"),
    ("wram", SRC / "include" / "wram.s"),
    ("hram", SRC / "include" / "hram.s"),
]

# Lab translation units, added only when LAB=1.
LAB_UNITS = [
    ("lab", ROOT / "src" / "lab" / "lab.asm"),
    ("lab_random", ROOT / "src" / "lab" / "random.asm"),
]

# Cartridge header for the Lab build. The stock cartridge is ROM-ONLY with
# ~51 usable free bytes, so expansion is arithmetic, not preference.
# See docs/architecture.md D5/D9.
MBC1_RAM_BATTERY = 0x03
MBC1_NO_RAM = 0x01
RAM_8KB = 0x02
RAM_NONE = 0x00


def run(cmd):
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if proc.stdout.strip():
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        print(proc.stderr.rstrip(), file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(str(c) for c in cmd)}")
    # rgbasm warnings are worth seeing even on success
    if proc.stderr.strip():
        print(proc.stderr.rstrip(), file=sys.stderr)


# Reserved by the cartridge header, filled by rgbfix after linking. The linker
# reports them as empty because no section claims them; writing there bricks the
# ROM (the boot ROM refuses to run if the logo does not match).
ROM0_RESERVED = ((0x0104, 0x0133, "Nintendo logo"),
                 (0x014D, 0x014F, "header checksums"))


def freespace(map_path: Path) -> None:
    """Per-bank free space, counting only bytes that could actually be used."""
    print("\nfree space:")
    bank, free, reserved = None, 0, 0

    def flush():
        if bank is None:
            return
        note = f"   ({reserved} reserved for the header)" if reserved else ""
        print(f"  {bank:<16} {free} bytes{note}")

    for line in map_path.read_text().splitlines():
        stripped = line.strip()
        if "bank #" in stripped and stripped.endswith(":") \
                and not stripped.startswith(("SECTION", "EMPTY", "TOTAL")):
            flush()
            bank, free, reserved = stripped.rstrip(":"), 0, 0
        elif stripped.startswith("EMPTY:") and bank:
            span = stripped.split("$", 1)[1].split(" ")[0]
            lo, hi = (int(x, 16) for x in span.split("-$"))
            size = hi - lo + 1
            if bank.startswith("ROM0") and any(lo >= a and hi <= b
                                               for a, b, _ in ROM0_RESERVED):
                reserved += size
            else:
                free += size
    flush()


def build_rom(lab: int, no_sram: bool = False):
    """Assemble, link and fix one ROM. Returns (rom path, map path, bytes)."""
    name = "tetrislab" if lab else "tetris"

    print(f"TetrisGYM-GB build  (LAB={lab})")

    print("toolchain:")
    tc = rgbds.ensure(BUILD)

    print("graphics:")
    gfx.build(tc / "rgbgfx", SRC, OBJ / "build", lab=bool(lab))

    print("assemble:")
    OBJ.mkdir(parents=True, exist_ok=True)
    objs = []
    units = UNITS + (LAB_UNITS if lab else [])
    for unit, path in units:
        obj = OBJ / f"{unit}.o"
        run([tc / "rgbasm", "-h", "-L", "-E",
             "-D", f"LAB={lab}",
             "-I", str(SRC) + "/", "-I", str(OBJ) + "/",
             "-I", str(ROOT / "src") + "/",
             "-o", obj, path])
        objs.append(obj)

    rom = BUILD / f"{name}.gb"
    sym = BUILD / f"{name}.sym"
    mapf = BUILD / f"{name}.map"

    print("link:")
    run([tc / "rgblink", "-n", sym, "-m", mapf, "-w", "-o", rom, *objs])
    if lab:
        mbc = MBC1_NO_RAM if no_sram else MBC1_RAM_BATTERY
        ram = RAM_NONE if no_sram else RAM_8KB
        run([tc / "rgbfix", "-v", "-p", "255",
             "-m", hex(mbc), "-r", hex(ram), rom])
    else:
        run([tc / "rgbfix", "-v", "-p", "255", rom])

    if lab and TREP_SOURCE.exists():
        # A map of ourselves, for Tolstoj's ROM editor. Nothing here runs TREP;
        # it reads this alongside the ROM. See docs/decisions/0012.
        n = trep.generate(TREP_SOURCE, sym, mapf, BUILD / f"{name}.trep.json")
        print(f"trep: {n} background maps -> build/{name}.trep.json")

    data = rom.read_bytes()
    print(f"\n{rom.relative_to(ROOT)}  {len(data)} bytes ({len(data) // 1024}KB)")
    print(f"  sha1 {hashlib.sha1(data).hexdigest()}")
    print(f"  md5  {hashlib.md5(data).hexdigest()}")
    print(f"  cart type ${data[0x147]:02X}  rom size ${data[0x148]:02X}  "
          f"ram size ${data[0x149]:02X}")
    return rom, mapf, data


def emit_patch(lab_rom: bytes) -> int:
    """Write the BPS the release ships. The source is our own byte-exact
    rebuild of the stock ROM, so producing a release needs no copy of it."""
    print("\npatch source:")
    _, _, stock = build_rom(lab=0)
    if hashlib.sha1(stock).hexdigest() != REFERENCE_SHA1:
        print("\nFAIL: patch source is not the stock ROM", file=sys.stderr)
        return 1

    bps = patch.create_bps(stock, lab_rom, b"tetris-lab-gb")
    out = BUILD / "tetrislab.bps"
    out.write_bytes(bps)

    restored = patch.apply(stock, bps)
    if restored != lab_rom:
        print("\nFAIL: the patch does not reproduce the ROM", file=sys.stderr)
        return 1

    print(f"\n{out.relative_to(ROOT)}  {len(bps)} bytes")
    print(f"  applies to sha1 {REFERENCE_SHA1}")
    print("  verified: applying it to the stock ROM reproduces this build")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", action="store_true",
                    help="build with LAB=0: must reproduce the stock ROM byte-exactly")
    ap.add_argument("--freespace", action="store_true", help="print per-bank free space")
    ap.add_argument("--no-sram", action="store_true",
                    help="build without cartridge RAM (cheaper board, no persistence)")
    ap.add_argument("--patch", action="store_true",
                    help="also write build/tetrislab.bps, the file releases ship")
    args = ap.parse_args()

    if args.patch and args.original:
        print("--patch builds the Lab ROM; it cannot be combined with --original",
              file=sys.stderr)
        return 2

    lab = 0 if args.original else 1
    rom, mapf, data = build_rom(lab, args.no_sram)

    if args.freespace:
        freespace(mapf)

    if args.original:
        if hashlib.sha1(data).hexdigest() != REFERENCE_SHA1:
            print(f"\nFAIL: expected sha1 {REFERENCE_SHA1}", file=sys.stderr)
            return 1
        print("\nOK: byte-exact match for Tetris (World) (Rev A)")

    if args.patch:
        return emit_patch(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
