; Lab core - everything this project adds lives in ROM banks 2 and up.
;
; Bank 0 and bank 1 remain the original game, byte for byte, except for the
; single declared hook in src/hooks/hooks.inc.

INCLUDE "include/hardware.inc"
INCLUDE "include/constants.s"   ; pure EQUs, safe in multiple translation units
INCLUDE "include/structs.s"     ; rb offsets, likewise

INCLUDE "lab/levels.inc"

; The version, in one place. It reaches the ROM's own string and the title
; screen's VERSION box from here, so a release bumps this line and nothing else.
; Three characters: the artwork leaves five cells and spends two of them on the
; gap after "VERSION", which is what keeps it reading as two words.
DEF LAB_VERSION EQUS "\"0.5\""

; ---------------------------------------------------------------------------
; The Lab, module by module.
;
; INCLUDE is textual, so these continue one section rather than each opening
; their own: same bank, same order, same bytes as when this was a single file.
; A section per module would let the linker reorder them and would break every
; `jr` that crosses a boundary. See docs/decisions/0011.
;
; Order matters. state.asm declares the WRAM and HRAM sections; dispatch.asm
; opens the bank 2 code section that everything after it continues.
; ---------------------------------------------------------------------------

INCLUDE "lab/state.asm"
INCLUDE "lab/dispatch.asm"
INCLUDE "lab/level_select.asm"
INCLUDE "lab/seed.asm"
INCLUDE "lab/high_scores.asm"
INCLUDE "lab/title.asm"
INCLUDE "lab/menu.asm"
INCLUDE "lab/trainers/transition.asm"
INCLUDE "lab/trainers/crunch.asm"
INCLUDE "lab/trainers/qtap.asm"
INCLUDE "lab/hz.asm"
INCLUDE "lab/gameplay.asm"
INCLUDE "lab/scoring.asm"
INCLUDE "lab/rendering.asm"
INCLUDE "lab/restart.asm"
