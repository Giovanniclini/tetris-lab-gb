; Declared edits to the original ROM banks 0 and 1.
;
; These are the ONLY places tetris-lab-gb is permitted to change original code.
; Every entry here is asserted by tests/test_expansion.py, which diffs banks 0-1
; against the reference build and fails if a single byte outside this table
; differs. Adding an entry is a significant change - see CLAUDE.md principle 3.
;
;   name              range           bytes  purpose
;   ----------------- --------------- -----  --------------------------------
;   HOOK_TRAMPOLINE   $00DA-$00FF        38  Lab far-call trampoline, placed in
;                                            the `ds $100-@, $ff` padding that
;                                            sits between the serial interrupt
;                                            code and the $0100 entry point.
;   LAB_GRAVITY_TABLE $000B-$0027        29  Extended 23-entry gravity table
;                                            (levels 0-22), in the padding that
;                                            follows the RST $08 vector.
;   HOOK_GRAVITY_PTR  $1AFB-$1AFC         2  Operand of `ld hl, .framesData`,
;                                            redirected to LabFramesData.
;   HOOK_STATE_TABLE  $031B-$031E         4  Two entries of ProcessGameState's
;                                            jump table ($10 A-type select
;                                            init, $11 main), routed through
;                                            LabStateHook. The handlers
;                                            themselves are untouched.
;   LAB_RESET_STUB    $0034-$003F        12  Far-call stub for instant restart,
;                                            in the padding between the RST $28
;                                            handler and the VBlank vector.
;   HOOK_MAINLOOP_RST $02D3-$02D5         3  MainLoop's soft-reset `jp z, Reset`
;                                            becomes `call z, LabResetStub`, so
;                                            the Lab can decline and carry on.
;   HOOK_INGAME_RST   $1C14-$1C15         2  Operand of the *other* soft-reset
;                                            check, inside
;                                            InGameCheckResetAndPause. This is
;                                            the one that fires while playing.
;   HOOK_STATE_TABLE4 $0303-$0304         2  Jump-table entry for $04, the
;                                            end-of-game screen, so the reset
;                                            combination is seen before that
;                                            handler acts on Start.
;   HOOK_RNG_PIECE    $2043-$2045         3  `ldh a,[rDIV] / ld b,a` in the
;                                            piece generator becomes
;                                            `call LabRandom` - three bytes for
;                                            three, so nothing shifts.
;   HOOK_RNG_BTYPE    $1B6F-$1B71         3  The same substitution for B-type's
;                                            starting garbage.
;   LAB_RANDOM        $7FC6-$7FEF        42  The LFSR itself, in the empty space
;                                            between the sound engine and the
;                                            sound thunks in bank 1. A new
;                                            section in a gap, not an insertion.
;   HOOK_STATE_TABLE15 $0325-$0326        2  Jump-table entry for $15, high
;                                            score name entry, so the reset
;                                            combination restarts the drill
;                                            rather than rebooting.
;   HOOK_STATE_TABLE0A $030F-$0310        2  Jump-table entry for $0A, in-game
;                                            init, so the configured seed is
;                                            loaded into the LFSR at the start
;                                            of every game - including an
;                                            instant restart, which must repeat
;                                            the sequence rather than continue.
;   HOOK_LEVEL_CAP    $245A               1  `ret z` becomes `ret nc`, so
;                                            levelling stops at 20 *or above*
;                                            rather than only on equality with
;                                            it. Identical for every level the
;                                            original can reach; an L or M start
;                                            never transitions. KLM makes the
;                                            same one-byte change.
;   HOOK_STATE_TABLE00 $02FB-$02FC       2  Jump-table entry for $00, the
;                                            per-frame gameplay state. The one
;                                            hook trainers act from while a game
;                                            is running - the transition trainer
;                                            needs it because the original's
;                                            in-game init clears the line count
;                                            after any earlier hook could set it.
;   HOOK_STATE_TABLE24 $0343-$0344       2  Jump-table entry for $24, the
;                                            copyright screen. Skipped whole:
;                                            8.5 s before the title on every
;                                            boot, and its only lasting effect
;                                            is a demo piece table that only the
;                                            attract demo reads.
;   HOOK_STATE_TABLE06 $0307-$030C       6  Jump-table entries for $06 (title
;                                            init), $07 (title main) and $08.
;                                            The title screen becomes the Lab
;                                            menu, drawn by $06 so the original
;                                            never appears even for a frame. $07 is the
;                                            screen, which becomes the Lab menu.
;                                            It has to be this state and no
;                                            other: SerialFunc0_titleScreen
;                                            ($0078) only assigns a multiplayer
;                                            role while hGameState is $07, and
;                                            bounces the game back to the title
;                                            from anywhere else. The only hook
;                                            that replaces an original handler
;                                            rather than chaining to it - and
;                                            for $08, which B on a level select
;                                            reaches, sent back to the menu so
;                                            the A-TYPE/B-TYPE screen the menu
;                                            replaced is never drawn.
;   HOOK_STATE_TABLE34 $0363-$0364       2  Jump-table entry for $34, the wait
;                                            before the rocket scene. Sent to
;                                            the plain game over screen, which
;                                            is where the original sends every
;                                            score that earns no celebration.
;                                            Skips the scene and the 2.4 s wait
;                                            in front of it.
;   HOOK_SCORE_CELLS  $01E8, $01F2,       4  The score is drawn one cell right,
;                     $23AD, $23C6           so its units digit lands in the
;                                            spare column 19 instead of leaving
;                                            it blank. Frees column 13 for the
;                                            seventh digit, and stops the number
;                                            shifting sideways when it passes a
;                                            million. One byte of the operand at
;                                            each of the four places the score
;                                            is drawn - screens 0 and 1, twice.
;   HOOK_SCORE_CAP    $0178-$017A         3  The clamp that pins the score at
;                                            999 999, replaced by a jump to a
;                                            carry handler. Three BCD bytes hold
;                                            six digits and the clamp stops them
;                                            wrapping to zero - it is the ceiling
;                                            of the storage, not a rule. The
;                                            three bytes after it are left as
;                                            they were and are unreachable.
;   LAB_BANK1_GFX     $7FF6-$7FFF        10  LabLoadMenuGfx, in the gap after
;                                            the sound thunks at the very end of
;                                            bank 1. Split from the section
;                                            below because neither gap is big
;                                            enough for both.
;   LAB_BANK1_THUNK   $6430-$644F        32  LoadAsciiAndMenuScreenGfx is in
;                                            bank 0 but reads Gfx_Ascii from
;                                            bank 1, so it cannot be called
;                                            while bank 2 is mapped. This thunk
;                                            is what the menu far-calls to load
;                                            its tileset. A new section in the
;                                            linker's own empty gap, not an
;                                            insertion.
;
; Nothing else in banks 0-1 may change.
;
; Note the shape of these: we redirect pointers and constants into space we
; reclaimed, we never *insert* into the original banks. Inserting shifts every
; byte after the insertion point - which is exactly why KLM is a 20KB binary
; diff for a feature we express in 54 bytes.

DEF HOOK_TRAMPOLINE_START EQU $00DA
DEF HOOK_TRAMPOLINE_END   EQU $00FF
DEF LAB_GRAVITY_START     EQU $000B
DEF LAB_GRAVITY_END       EQU $0027
