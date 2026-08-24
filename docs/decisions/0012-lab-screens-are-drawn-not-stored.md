# 12. Lab screens are drawn, not stored — and TREP designs them

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
it is an external editor that reads what we publish.

**Screens the Lab owns are drawn at runtime, not stored as layouts.** TREP is
where they get designed; the design arrives as Lab drawing code, not as a `.bin`
that replaces vendored data.

## Why not store them

An edited layout would have to go somewhere, and both answers are worse:

* **Overwriting `src/original/data/*.bin` breaks the ground truth.** That data
  has no `IF LAB` guards, so it is shared with the `LAB=0` build — change a
  screen and `build.py --original` stops reproducing the stock ROM. Principle 4
  says that makes the change wrong, not the test.
* **A guarded Lab copy has nowhere to live.** The layouts sit in bank 0, whose
  only free bytes are the Nintendo logo and the header checksums. A second copy
  of a 360-byte screen does not fit, and bank 2 is not reachable from the
  original's `CopyLayoutToScreen0`, which runs with bank 1 mapped.

Drawing at runtime costs neither. It is also what the menu already does, so this
records existing practice rather than inventing any.

## Consequences

* **TREP is a design tool for Lab screens and an editor for original ones.** An
  export drops straight into an original screen only if we ever decide to change
  one wholesale, which would need its own justification.
* **Dimensions are load-bearing and unchecked by TREP.** Layouts carry no `.end`
  label, so TREP reads `width * height` bytes from the symbol and believes the
  manifest. A wrong figure shows a plausible wrong screen with no error, so
  `tests/test_trep.py` checks every one against the data on disk.
* **`-E` is load-bearing too.** Most of the labels TREP wants are declared with a
  single colon, local to their object file; they reach the `.sym` only because
  `rgbasm` runs with `-E`. Removing it breaks TREP silently, so a test asserts
  the flag is still there. This is also why Tolstoj's request to add second
  colons to `Gfx_MenuScreens` and `Layout_ATypeInGame` was declined: all 20
  symbols his manifest names are already exported, and `src/original/` stays
  untouched.
* **Exported binaries are unreviewable.** If a `.bin` ever does land here, it
  needs something a reviewer can see — a regenerated screenshot, or the PNG
  beside it.
