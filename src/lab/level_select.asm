; --------------------------------------------------------------------------
; The A-type level select
;
; The original's 0-9 grid, extended with a level field to its right offering the
; levels the grid cannot: A-M. Two fields, no overlap - a level appears in one
; place or the other, never both.
; Three state handlers - init, main, and a pass after the original's own -
; plus the field painting they share.
; --------------------------------------------------------------------------

LabLevelSelectInit::
; File the score first, while hATypeLevel still says the level that was played.
; Ours rather than the original's, because a seventh digit changes the ranking.
; It leaves wScoreBCD zeroed either way, so the original's own call a moment
; later finds nothing and cannot file the same game twice.
	call LabFileHighScore

; hATypeLevel may hold a level above the grid, set last time a game started.
	ldh  a, [hATypeLevel]
	cp   GRID_LAST + 1
	jr   nc, .aboveGrid

	ld   a, FOCUS_GRID
	ld   [wLabFocus], a
	ld   a, PICKER_FIRST            ; the first level the grid cannot offer
	ld   [wLabPickerLevel], a
	jr   .pending

.aboveGrid:
	ld   [wLabPickerLevel], a
	ld   a, FOCUS_LEVEL
	ld   [wLabFocus], a

	ld   a, GRID_LAST
	ldh  [hATypeLevel], a           ; keep the grid cursor somewhere valid

.pending:
	ld   a, 1
	ld   [wLabRedrawPending], a
	ret


LabLevelSelectMain::
; While the reset combination is held, do not let the menu act on Start. It is
; part of the combination, so the menu would start a game that is then rebooted
; a frame later - you see it flash up on screen before the logo returns.
	call LabResetComboHeld
	jr   nz, .notResetting

	ldh  a, [hButtonsPressed]
	res  PADB_START, a
	res  PADB_A, a
	ldh  [hButtonsPressed], a
	ret

.notResetting:
	ld   a, [wLabRedrawPending]
	and  a
	jr   z, .readInput
	xor  a
	ld   [wLabRedrawPending], a
	call LabDrawHearts
	call LabUpdateHighScores        ; the original's init painted the grid level
	call LabPaintFields

.readInput:
	ldh  a, [hButtonsPressed]
	ld   c, a

; Select toggles hard mode ("hearts"). The original arms it with an
; undocumented Down+Start on the title screen, two screens earlier, with no
; feedback until a heart appears here; it never tests Select on this screen.
	bit  PADB_SELECT, c
	jr   z, .afterSelect

	ldh  a, [hIsHardMode]
	and  a
	ld   a, 0
	jr   nz, .storeHearts
	ld   a, 1

.storeHearts:
	ldh  [hIsHardMode], a
	call LabDrawHearts

.afterSelect:
	ld   a, [wLabFocus]
	and  a
	jr   nz, .levelFocus

; --- the grid has focus: the only thing we add is Right on the last cell ---
.gridFocus:
	bit  PADB_RIGHT, c
	ret  z
	ldh  a, [hATypeLevel]
	cp   GRID_LAST
	ret  nz
	ld   a, FOCUS_LEVEL
	ld   [wLabFocus], a
	jr   .consume

; --- the level field has focus ---
; Every direction that lands here is swallowed, whether or not it changed
; anything: the original would otherwise move the grid cursor underneath us.
.levelFocus:
	bit  PADB_LEFT, c
	jr   z, .levelNotLeft
	xor  a                          ; FOCUS_GRID
	ld   [wLabFocus], a
	call LabShowGridCursor
	jr   .consume

.levelNotLeft:
	bit  PADB_RIGHT, c
	jr   nz, .consume               ; nothing to the right of the level now

.levelNotRight:
	bit  PADB_UP, c
	jr   z, .levelNotUp
	ld   a, [wLabPickerLevel]
	cp   MAX_LEVEL
	jr   nc, .consume               ; already at M
	inc  a
	ld   [wLabPickerLevel], a
	jr   .consume

.levelNotUp:
	bit  PADB_DOWN, c
	ret  z
	ld   a, [wLabPickerLevel]
	cp   PICKER_FIRST + 1
	jr   c, .consume                ; already at A; 0-9 are the grid's to offer
	dec  a
	ld   [wLabPickerLevel], a
	jr   .consume

.consume:
	ldh  a, [hButtonsPressed]
	res  PADB_LEFT, a
	res  PADB_RIGHT, a
	res  PADB_UP, a
	res  PADB_DOWN, a
	ldh  [hButtonsPressed], a
	ld   a, SND_MOVING_SELECTION
	ld   [wSquareSoundToPlay], a
	call LabUpdateHighScores
	jp   LabPaintFields


; Runs after the original handler.
LabLevelSelectPost::
	ldh  a, [hGameState]
	cp   GS_A_TYPE_SELECTION_MAIN
	jr   nz, .leavingScreen

	call LabRefreshHiScoreMillions

	ld   a, [wLabFocus]
	and  a
	ret  z                          ; grid has focus: nothing to correct

; Hide the grid cursor - it draws the character for hATypeLevel, which is not
; what these fields show - and push that through to OAM, because the original
; has already copied the specs by the time we run.
	ld   a, SPRITE_SPEC_HIDDEN
	ld   [wSpriteSpecs + SPR_SPEC_Hidden], a
	call Copy2SpriteSpecsToShadowOam

; Hearts are min(level + 10, 20). Above level 20 that ceiling clamps downward
; and makes the game slower, so hearts are turned off up there rather than
; changing the original formula. See docs/existing-hacks.md 3.2b.
	ld   a, [wLabPickerLevel]
	cp   21
	jr   c, .blink
	ldh  a, [hIsHardMode]
	and  a
	jr   z, .blink
	xor  a
	ldh  [hIsHardMode], a
	call LabDrawHearts

.blink:
	ld   hl, wLabBlinkTimer
	inc  [hl]
	ld   a, [hl]
	and  $10
	ld   b, a
	ld   a, [wLabBlinkPhase]
	cp   b
	ret  z
	ld   a, b
	ld   [wLabBlinkPhase], a
	jp   LabPaintFields

; The original has handed over - to the game, or back a screen. hATypeLevel has
; been holding a grid index so the original cursor code kept working; now that
; nothing else reads it as an index, fold in the level field.
.leavingScreen:
	ld   a, [wLabFocus]
	and  a
	ret  z                          ; grid has focus: the cursor is the level
	ld   a, [wLabPickerLevel]
	ldh  [hATypeLevel], a
	ret


LabShowGridCursor::
	xor  a
	ld   [wSpriteSpecs + SPR_SPEC_Hidden], a
	ld   de, wSpriteSpecs + SPR_SPEC_BaseYOffset
	ld   hl, ATypeLevelsCoords
	ldh  a, [hATypeLevel]
	call SetNumberSpecStructsCoordsAndSpecIdxFromHLtable
	jp   Copy2SpriteSpecsToShadowOam


; Paint the level field, the SEED label and the four seed digits, blanking
; whichever field has focus while the blink phase is off. Ten tilemap writes at
; most, so it simply waits for VBlank - the original does the same in
; HandleLockdownTransferToTilemap.
; The high score name is typed on the level select's own screen, and that
; screen is the original's - it knows nothing about the field beside the grid.
; So while you type, the level you just played is nowhere on it, and the grid
; cursor sits on the 9 that hATypeLevel was clamped to: the screen says you
; played level 9 whatever you actually played.
;
; Steady rather than blinking. The blink means "this field has focus", and while
; a name is being typed the focus is the name.
;
; The grid cursor has to go with it, for the same reason it does on the level
; select itself: it is a sprite that draws the character for hATypeLevel, and
; hATypeLevel was clamped into the grid on the way here. Left alone it sits on
; the 9 while the picker says C, and the screen offers two answers to which
; level this was.
LabPaintPickerSteady::
	ld   a, [wLabPickerLevel]
	ld   hl, PICKER_CELL
	call LabPutTile

	ld   a, [wLabFocus]
	and  a
	ret  z                          ; the grid really is the answer: leave it

	ld   a, SPRITE_SPEC_HIDDEN
	ld   [wSpriteSpecs + SPR_SPEC_Hidden], a
	jp   Copy2SpriteSpecsToShadowOam


LabPaintFields::
.waitVBlank:
	ldh  a, [rLY]
	cp   SCRN_Y
	jr   c, .waitVBlank

; level field
	ld   a, [wLabPickerLevel]
	ld   b, FOCUS_LEVEL
	call LabBlankIfFocused
	ld   [PICKER_CELL], a

	ret


; A = TILE_BLANK when field B has focus and the blink is off, else A unchanged.
LabBlankIfFocused::
	push af
	ld   a, [wLabBlinkPhase]
	and  a
	jr   nz, .keep                  ; blink on: draw normally
	ld   a, [wLabFocus]
	cp   b
	jr   nz, .keep
	pop  af
	ld   a, TILE_BLANK
	ret

.keep:
	pop  af
	ret
