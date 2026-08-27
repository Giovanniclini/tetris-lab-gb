# 12. TREP designs the screens, and Lab layouts live in bank 2

**Status:** accepted, 2026-08-23

## Context

Tolstoj's ROM editor, [TREP](https://tolstoj-82.github.io/apps/trep/), opens a
built ROM and shows its tilesets and background maps as editable pictures. He
offered to do the project's visuals with it, which is the part this project is
worst at. TREP needs four things: the `.gb`, the `.sym`, the `.map` and a
metadata file describing where the maps are.

We already had three. He wrote the manifest for the fourth.

## Decision

**The build publishes a map of itself.** `tetrislab.trep-source.json` catalogues
the tilesets and background maps; `tools/trep.py` resolves it against the
`.sym`/`.map` into `build/tetrislab.trep.json`. Nothing in the build runs TREP —
it is an external editor that reads what we publish. Both patch channels carry
the three files beside the patch.

**A Lab screen's static background is a layout in `src/lab/data/`**, INCBINed
into bank 2 beside the code that paints it and catalogued like any other map, so
it can be designed in TREP and arrive back as a `.bin`. Everything that changes —
labels, cursors, values — is still drawn at runtime.

**A Lab screen may bring its own tiles too**: a PNG in `src/lab/gfx/`, converted
by the same `tools/gfx.py` pipeline with its own declared byte count, INCBINed
into bank 2 and copied over VRAM after the original tileset is loaded. The LCD is
off during a screen's paint, so the second pass is free, and the screens that
load the original tileset are unaffected.

**`src/original/data/` stays vendored and unedited.**

## Where a layout can live

* **Not in `src/original/data/`.** That data has no `IF LAB` guards, so it is
  shared with the `LAB=0` build: editing a screen there stops `build.py
  --original` reproducing the stock ROM. Principle 4 says that makes the edit
  wrong, not the test.
* **Not in bank 0.** Its only free bytes are the Nintendo logo and the header
  checksums.
* **Bank 2**, which has both the room and the reach. Lab code paints Lab
  screens, and it can read its own bank directly. `CopyLayoutToScreen0`
  (`$27EB`) is bank-0 code that reads from `de` and switches no banks, so bank-2
  code may call it with a bank-2 source (ADR 0001).

## Consequences

* **TREP is a design tool for Lab screens and an editor for original ones.** An
  export drops straight into a Lab screen. Dropping one into an original screen
  would need its own justification.
* **The font is 39 tiles, so a tileset after it starts at `$27`.** Measured out
  of VRAM rather than counted, because the menu's loader copies ten further tiles
  in between and it is easy to derive the wrong number.
* **A cursor is whatever the screen it sits on actually has.** The title screen's
  is the arrow Tolstoj drew into the artwork, moved between cells; a sprite over
  it would be a second cursor, with only one of them moving. The menu's tileset
  has no arrow at all — the original keeps one in the title-screen tileset — so
  the menu copies that single tile into `$FF`, past anything its layout draws
  and rewritten on every screen entry.
* **A map is 20x18**, the shape every original screen uses. The VBlank handler
  zeroes `rSCX`/`rSCY` every frame (`$01FF`), so nothing outside those 20
  columns is ever visible and a map need not cover the 32-wide tilemap.
* **Dimensions are load-bearing and unchecked by TREP.** Layouts carry no `.end`
  label, so TREP reads `width * height` bytes from the symbol and believes the
  manifest. A wrong figure shows a plausible wrong screen with no error, so
  `tests/test_trep.py` checks every one — against the `.bin` where there is one,
  and against the span to the next symbol where there is not.
* **`-E` is load-bearing too.** Most of the labels TREP wants are declared with a
  single colon, local to their object file; they reach the `.sym` only because
  `rgbasm` runs with `-E`. Removing it breaks TREP silently, so a test asserts
  the flag is still there. This is also why Tolstoj's request to add second
  colons to `Gfx_MenuScreens` and `Layout_ATypeInGame` was declined: all 20
  symbols his manifest names are already exported, and `src/original/` stays
  untouched.
* **Exported binaries are unreviewable.** A `.bin` needs something a reviewer can
  see — a regenerated screenshot, or the PNG beside it.
* **A new background map starts as the screen already on display**, so the
  tilemap must come out identical before and after it is introduced. That
  separates the wiring from the design: if the screen changes later, it is the
  design.
