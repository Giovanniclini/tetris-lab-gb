#!/usr/bin/env python3
"""Milestone 0.5: the cartridge is expanded, the original game is not touched.

    python3 tests/test_expansion.py        (also collectable by pytest)

The load-bearing test here is `test_original_banks_only_change_where_declared`.
It is what lets us restructure freely: if a refactor ever alters a byte of
original game code, this fails immediately and names the address.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Every permitted difference in banks 0-1, from src/hooks/hooks.inc plus the
# header fields the MBC1 conversion necessarily rewrites.
ALLOWED_RANGES = [
    (0x000B, 0x0027, "LAB_GRAVITY_TABLE - 23-entry gravity table in RST $08 padding"),
    (0x00DA, 0x00FF, "HOOK_TRAMPOLINE - Lab far-call trampoline in entry-point padding"),
    (0x0034, 0x003F, "LAB_RESET_STUB - instant-restart far-call stub"),
    (0x02D3, 0x02D5, "HOOK_MAINLOOP_RST - MainLoop reset check routed via the Lab"),
    (0x02FB, 0x02FC, "HOOK_STATE_TABLE_00 - per-frame gameplay state, for trainers"),
    (0x0303, 0x0304, "HOOK_STATE_TABLE_04 - level-ended state routed via the Lab"),
    (0x0307, 0x030C, "HOOK_STATE_TABLE_06/07/08 - the title screen is the Lab menu, "
                     "drawn by $06 so the original never appears; B from a level "
                     "select comes back to it"),
    (0x0363, 0x0364, "HOOK_STATE_TABLE34 - the rocket scene, skipped whole"),
    (0x01E8, 0x01E8, "HOOK_SCORE_CELLS - score drawn one cell right, screen 0"),
    (0x01F2, 0x01F2, "HOOK_SCORE_CELLS - score drawn one cell right, screen 1"),
    (0x23AD, 0x23AD, "HOOK_SCORE_CELLS - score drawn one cell right, screen 1"),
    (0x23C6, 0x23C6, "HOOK_SCORE_CELLS - score drawn one cell right, screen 0"),
    (0x0178, 0x017A, "HOOK_SCORE_CAP - the 999,999 clamp redirected to a carry handler"),
    (0x7FF6, 0x7FFF, "LAB_BANK1_GFX - the menu tileset thunk, in the gap past the sound thunks"),
    (0x6430, 0x644F, "LAB_BANK1_THUNK - the score carry handler, reached during gameplay"),
    (0x030F, 0x0310, "HOOK_STATE_TABLE_0A - in-game init routed via the Lab"),
    (0x031B, 0x031E, "HOOK_STATE_TABLE - A-type selection states routed via the Lab"),
    (0x0325, 0x0326, "HOOK_STATE_TABLE_15 - name entry routed via the Lab"),
    (0x0343, 0x0344, "HOOK_STATE_TABLE_24 - copyright screen skipped entirely"),
    (0x1B6F, 0x1B71, "HOOK_RNG_BTYPE - B-type garbage draw routed via LabRandom"),
    (0x1C14, 0x1C15, "HOOK_INGAME_RST - in-game reset check routed via the Lab"),
    (0x2043, 0x2045, "HOOK_RNG_PIECE - piece generator draw routed via LabRandom"),
    (0x7FC6, 0x7FEF, "LAB_RANDOM - the LFSR, in bank 1's empty space"),
    (0x1AFB, 0x1AFC, "HOOK_GRAVITY_PTR - table pointer redirected to LabFramesData"),
    (0x245A, 0x245A, "HOOK_LEVEL_CAP - `ret z` -> `ret nc`, so L and M never transition"),
    (0x0147, 0x0147, "cartridge type -> MBC1+RAM+BATTERY"),
    (0x0148, 0x0148, "ROM size -> 64KB"),
    (0x0149, 0x0149, "RAM size -> 8KB"),
    (0x014D, 0x014D, "header checksum (recomputed by rgbfix)"),
    (0x014E, 0x014F, "global checksum (recomputed by rgbfix)"),
]

CART_MBC1_RAM_BATTERY = 0x03
ROM_SIZE_64KB = 0x01
RAM_SIZE_8KB = 0x02


def _build(*args) -> bytes:
    proc = subprocess.run(
        [sys.executable, "build.py", *args], cwd=ROOT, capture_output=True, text=True
    )
    assert proc.returncode == 0, f"build failed:\n{proc.stdout}\n{proc.stderr}"
    name = "tetris.gb" if "--original" in args else "tetrislab.gb"
    return (ROOT / "build" / name).read_bytes()


def test_original_banks_only_change_where_declared():
    """The whole architecture in one assertion.

    Banks 0 and 1 are the original game. Any byte that differs between the
    stock build and the Lab build must be covered by an entry in
    src/hooks/hooks.inc. An undeclared difference means we changed original
    gameplay code, which is the one thing this project must never do silently.
    """
    ref, lab = _build("--original"), _build()

    def allowed(addr):
        return any(lo <= addr <= hi for lo, hi, _ in ALLOWED_RANGES)

    undeclared = [i for i in range(0x8000) if ref[i] != lab[i] and not allowed(i)]
    assert not undeclared, (
        f"{len(undeclared)} undeclared byte(s) changed in the original banks, "
        f"first at ${undeclared[0]:04X}. Either revert the change, or declare "
        f"it in src/hooks/hooks.inc and justify it in the commit."
    )


def test_trampoline_fits_its_declared_padding():
    """The trampoline must not overflow into the $0100 entry point."""
    ref, lab = _build("--original"), _build()
    changed = [i for i in range(0x00DA, 0x0100) if ref[i] != lab[i]]
    assert changed, "trampoline is missing - nothing changed in the padding"
    assert max(changed) <= 0x00FF, "trampoline overflowed past $00FF"
    used = max(changed) - 0x00DA + 1
    assert used <= 38, f"trampoline uses {used} of 38 available bytes"


def test_level_cap_stops_at_twenty_or_above():
    """docs/existing-hacks.md 3.2. Stock stops levelling only on *equality* with
    $14, which is fine when 20 is the highest level there is. With L and M
    selectable it is not: 21 never equals 20, so it keeps climbing off the end
    of the gravity table into code.

    `ret nc` instead of `ret z` - identical for every level the original can
    reach, and an L or M start never transitions. This is what KLM does too, one
    byte different from stock; our first reading of KLM missed it."""
    ref, lab = _build("--original"), _build()
    assert ref[0x2458:0x245B] == bytes((0xFE, 0x14, 0xC8)), "stock: cp $14 / ret z"
    assert lab[0x2458:0x245B] == bytes((0xFE, 0x14, 0xD0)), (
        f"Lab should be cp $14 / ret nc, got {lab[0x2458:0x245B].hex(' ')}"
    )


def test_extended_gravity_table_contents():
    """The 23-entry table must match stock for 0-20 and KLM for L and M."""
    ref, lab = _build("--original"), _build()
    table = lab[0x000B:0x000B + 23]
    assert list(table[:21]) == list(ref[0x1B06:0x1B06 + 21]), "levels 0-20 changed"
    assert table[21] == 0x01, "L should be 2 frames/row"
    assert table[22] == 0x00, "M should be 1 frame/row (the engine ceiling)"


def test_lab_cartridge_header():
    d = _build()
    assert d[0x147] == CART_MBC1_RAM_BATTERY, f"cart type ${d[0x147]:02X}"
    assert d[0x148] == ROM_SIZE_64KB, f"ROM size ${d[0x148]:02X}"
    assert d[0x149] == RAM_SIZE_8KB, f"RAM size ${d[0x149]:02X}"
    assert len(d) == 64 * 1024, f"{len(d)} bytes"


def test_no_sram_variant_builds():
    """D9: SRAM must be optional - a battery adds cost and eventually dies."""
    d = _build("--no-sram")
    assert d[0x147] == 0x01, "cart type should be MBC1 without RAM"
    assert d[0x149] == 0x00, "RAM size should be none"


def test_the_release_patch_reproduces_the_rom():
    """Releases ship a patch and nothing else (CLAUDE.md principle 10), so the
    patch - not the ROM - is what has to be right."""
    sys.path.insert(0, str(ROOT))
    from tools import patch

    lab = _build("--patch")
    bps = (ROOT / "build" / "tetrislab.bps").read_bytes()
    stock = (ROOT / "build" / "tetris.gb").read_bytes()

    assert bps[:4] == b"BPS1", f"not a BPS patch: {bps[:4]!r}"
    assert len(bps) < len(lab) // 8, (
        f"patch is {len(bps)} bytes against a {len(lab)}-byte ROM - "
        "that is large enough to be carrying game data"
    )
    assert patch.apply(stock, bps) == lab, "the patch does not reproduce the ROM"


def test_original_build_still_byte_exact():
    """Milestone 0's guarantee must survive Milestone 0.5."""
    d = _build("--original")
    assert hashlib.sha1(d).hexdigest() == "74591cc9501af93873f9a5d3eb12da12c0723bbc"


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
