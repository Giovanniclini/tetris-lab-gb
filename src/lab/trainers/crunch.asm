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
	ld   a, GAME_SCREEN_ROWS
	ld   [wLabCrunchRowsToSend], a
	ret


; The buffer is the game's collision map; this is the same columns on the screen.
;
; Not by setting hRowsShiftingDownState, which is what the original's own
; FillGameScreenBufferWithTileAandSetToVramTransfer does. That is the row-shift
; state machine, and borrowing it while a piece is live costs three things: the
; piece freezes for as long as the walk takes ($208D and $20BA both return early
; while it runs), the walls visibly grow a row at a time, and finishing it looks
; to the game like a completed line clear - so it spawns the next piece over the
; one you were holding. TetrisGYM never meets this because advanceGameCrunch
; runs at game init, before any piece exists.
;
; So the rows go up a few at a time, on our own counter, the way CLAUDE.md 11
; asks Lab rendering to work: a queue with a per-frame budget. Three rows a
; frame puts every column on screen inside a tenth of a second.
DEF CRUNCH_ROWS_PER_FRAME EQU 3

LabCrunchSendRows::
	ld   a, [wLabCrunchRowsToSend]
	and  a
	ret  z

	ld   c, CRUNCH_ROWS_PER_FRAME
.nextRow:
	ld   a, [wLabCrunchRowsToSend]
	and  a
	ret  z
	dec  a
	ld   [wLabCrunchRowsToSend], a

; row a of the playfield, in both the buffer and screen 0
	ld   h, 0
	ld   l, a
	add  hl, hl
	add  hl, hl
	add  hl, hl
	add  hl, hl
	add  hl, hl                     ; * GB_TILE_WIDTH
	push hl
	ld   de, _SCRN0 + 2
	add  hl, de
	push hl
	ld   a, [wLabCrunch]
	rrca
	rrca
	and  $03
	jr   z, .rightSide
	ld   b, a
.leftLoop:
	ld   a, TILE_SOLID_BLOCK
	call LabPutTile
	inc  hl
	dec  b
	jr   nz, .leftLoop

.rightSide:
	pop  hl
	ld   a, [wLabCrunch]
	and  $03
	jr   z, .rowSent
	ld   b, a
	ld   de, GAME_SQUARE_WIDTH - 1
	add  hl, de
.rightLoop:
	ld   a, TILE_SOLID_BLOCK
	call LabPutTile
	dec  hl
	dec  b
	jr   nz, .rightLoop

.rowSent:
	pop  hl
	dec  c
	jr   nz, .nextRow
	ret
