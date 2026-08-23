# 11. Lab code is many small files, textually included

**Status:** accepted, 2026-08-23

## Context

`src/lab/lab.asm` had grown to 1973 lines and 46 routines covering the state
dispatch, the menu, the level select, seeds, high scores, drills, scoring,
rendering and restart. Finding anything meant scrolling.

## Decision

Split it into one module per responsibility, each `INCLUDE`d by a short
top-level `lab.asm` that reads as a table of contents.

**One `SECTION`, textual includes — not one section per module.** `INCLUDE` is
textual, so the modules continue the section the top-level file opened. Nothing
about the output changes: same bank, same addresses, same order, same bytes.

The alternative — a floating `SECTION` per module — was rejected. It would let
the linker reorder code, which moves every routine, and it would break every
`jr` that crosses a module boundary, turning it into a `jp`: different bytes and
different cycle counts, for no gain.

## Consequences

* **The refactor is verifiable by hash.** A pure split must leave
  `build/tetrislab.gb` byte-identical. Anything else is a bug in the split, and
  says so immediately. This was confirmed before committing to the approach.
* **Module boundaries follow the existing order**, because reordering would move
  code. Where that puts a routine in a module it does not logically belong to,
  the module comment says so rather than the code moving. Reordering is a
  separate change with its own justification, not a side effect of tidying.
* **Constants and local labels keep working.** One translation unit means `DEF`
  is still visible everywhere and `.local` labels still scope to the global
  above them. Splitting mid-routine would break the latter, so cuts are only
  ever at routine boundaries.
* **Include order is the dependency order**, and it is the whole content of
  `lab.asm`. There is nowhere else to look for it.
