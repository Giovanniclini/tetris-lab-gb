; --------------------------------------------------------------------------
; CRUNCH
;
; Narrow the playfield to force cramped stacking, matching TetrisGYM's mode of
; the same name (src/modes/crunch.asm) - including the value, so a number means
; the same shape on both ROMs. Every 4 takes a column off the left, every 1
; takes one off the right, and the right wraps after 3:
;
;   0 = 0 left 0 right      A = 2 left 2 right      F = 3 left 3 right
;
; The columns are filled with blocks, not walls. That is what makes a row
; "complete" when only the narrow gap is full: the check scans for empty cells
; and finds none in the filled columns.
;
; Which is also why they have to be refilled. A line clear shifts the ten
; playfield columns down ($2285 clears GAME_SQUARE_WIDTH cells from column 2),
; so it eats the crunch columns along with everything else - TetrisGYM re-runs
; advanceSides inside playState_checkForCompletedRows for the same reason. Ours
; refills from the per-frame gameplay hook, which also keeps collision right:
; the falling piece tests against this buffer, so the blocks are the wall.
; --------------------------------------------------------------------------

DEF CRUNCH_MAX EQU $0f


; The blocks, into the buffer. Cheap enough for every frame - plain WRAM, no
; waiting on the LCD - and doing it unconditionally means nothing has to work
; out when a clear finished.
LabCrunchFill::
	ld   a, [wLabMode]
	cp   MODE_CRUNCH
	ret  nz
	ld   a, [wLabCrunch]
	and  a
	ret  z

	ld   hl, wGameScreenBuffer + 2
	ld   c, GAME_SCREEN_ROWS

.nextRow:
	push hl

	ld   a, [wLabCrunch]
	rrca
	rrca
	and  $03                        ; every 4 is a column off the left
	jr   z, .rightSide
	ld   b, a
	ld   a, TILE_SOLID_BLOCK
.leftLoop:
	ld   [hl+], a
	dec  b
	jr   nz, .leftLoop

.rightSide:
	pop  hl
	push hl
	ld   a, [wLabCrunch]
	and  $03                        ; and every 1 a column off the right
	jr   z, .rowDone
	ld   b, a
	ld   de, GAME_SQUARE_WIDTH - 1
	add  hl, de
	ld   a, TILE_SOLID_BLOCK
.rightLoop:
	ld   [hl-], a
	dec  b
	jr   nz, .rightLoop

.rowDone:
	pop  hl
	ld   de, GB_TILE_WIDTH
	add  hl, de
	dec  c
	jr   nz, .nextRow
	ret


LabCrunchArm::
	ld   a, [wLabMode]
	cp   MODE_CRUNCH
	ret  nz
	ld   a, 1
	ld   [wLabCrunchPending], a
	ret


; On the first gameplay frame, not at the game init: that init clears the
; playfield, so filling it beforehand achieves nothing and the transfer request
; is spent on an empty screen. Same reason the transition trainer waits.
;
; Filling the buffer is not enough by itself - the screen has to be told.
; Setting the shift state is the request the original's own
; FillGameScreenBufferWithTileAandSetToVramTransfer ($1FD7) makes, and its
; row-copy machinery walks every row up to VRAM from there.
LabCrunchApply::
	ld   a, [wLabCrunchPending]
	and  a
	ret  z
	xor  a
	ld   [wLabCrunchPending], a

	call LabCrunchFill
	ld   a, [wLabCrunch]
	and  a
	ret  z
	ld   a, ROWS_SHIFTING_DOWN_ROW_START
	ldh  [hRowsShiftingDownState], a
	ret
