; --------------------------------------------------------------------------
; Trainers
;
; TRANSITION so far: start a game a set number of lines short of a level
; change, to drill the speed increase. Armed at game init, applied on the
; first gameplay frame - the original's init clears the line count, so
; setting it any earlier achieves nothing.
; --------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; Transition trainer
;
; TetrisGYM's TRANSITION (src/gamemodestate/initstate.asm, transitionModeSetup)
; fills the line counter up to the last ten-line boundary before the level
; advances, so you start one clear away from the speed change.
;
; The Game Boy's transition is that boundary: the original treats your starting
; level as the number of tens you must clear, so a level 9 start transitions at
; 100 lines. Ten short of it is 90.
;
; The one thing not carried over is TetrisGYM's score preset. Its modifier
; exists so the score and pace readouts look like a real run at that point;
; the Game Boy has no pace display and its transition point moves with the
; start level, so there is nothing for the number to mean here.
; ---------------------------------------------------------------------------

LabArmDrill::
	ld   a, [wLabMode]
	cp   MODE_TRANSITION
	ret  nz
	ld   a, 1
	ld   [wLabDrillPending], a
	ret


; The original's in-game init clears the line counter, so this runs on the first
; gameplay frame instead - after it, not before.
LabDrillApply::
	ld   a, [wLabDrillPending]
	and  a
	ret  z
	xor  a
	ld   [wLabDrillPending], a

; hATypeLinesThresholdToPassForNextLevel holds the start level, which is also
; the number of tens that must be cleared to transition. One ten short of it is
; where the drill begins.
; The game levels up when lines/10 exceeds the level, so a level 9 start
; transitions at 100 lines. Ten short of that is 90 - the level's own count of
; tens. Level 0 transitions at 10, so its drill preloads nothing.
	ldh  a, [hATypeLinesThresholdToPassForNextLevel]
	and  a
	ret  z
	ld   b, a                       ; tens to preload, 1-22

	xor  a
	ld   c, a                       ; hundreds, BCD
	ld   d, a                       ; tens and units, BCD

.addTen:
	ld   a, b
	and  a
	jr   z, .store
	dec  b
	ld   a, d
	add  $10
	daa
	ld   d, a
	jr   nc, .addTen
	ld   a, c
	add  1
	daa
	ld   c, a
	jr   .addTen

.store:
	ld   a, d
	ldh  [hNumLinesCompletedBCD], a
	ld   a, c
	ldh  [hNumLinesCompletedBCD+1], a

; Repaint the readout: the original only redraws it on a line clear, so without
; this the game shows 000 until the first one.
	jp   LabDrillPaintLines


; The four LINES digits, leading zeros blanked, exactly as the original renders
; them. Not DisplayBCDNum2CDigits: that writes the tilemap with a bare
; `ld [hl+], a`, which is correct for the original - it only ever calls it with
; the LCD idle - and drops writes anywhere else.
LabDrillPaintLines::
	ldh  a, [hNumLinesCompletedBCD + 1]
	ld   d, a
	ldh  a, [hNumLinesCompletedBCD]
	ld   e, a
	ld   hl, _SCRN0 + $14e
	ld   c, 0                       ; set once a digit has been drawn

	ld   a, d
	swap a
	call LabDrillDigit
	ld   a, d
	call LabDrillDigit
	ld   a, e
	swap a
	call LabDrillDigit
	ld   c, 1                       ; the units digit always shows
	ld   a, e
	; falls through

LabDrillDigit:
	and  $0f
	jr   nz, .visible

	ld   a, c
	and  a
	ld   a, TILE_EMPTY              ; nothing drawn yet: a leading zero
	jr   z, .put
	ld   a, TILE_0                  ; inside the number: a real zero
	jr   .put

.visible:
	ld   c, 1

.put:
	call LabPutTile
	inc  hl
	ret
