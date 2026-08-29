; --------------------------------------------------------------------------
; The Lab menu
;
; The game type screen, replaced. One scrolling-list-shaped menu of modes and
; settings, modelled on TetrisGYM's game type menu (ADR 0007). The link
; handshake is not here: 2 PLAYER is chosen on the title screen, which is the
; only state the original's serial code will assign a role in.
; --------------------------------------------------------------------------

; The menu screen is painted by the init state and nowhere else, the way every
; original screen works.
LabMenu::
	call LabMenuInput
	jp   LabMenuRepaint


LabMenuInput::
	ldh  a, [hButtonsPressed]
	ld   c, a

; The seed needs a cursor of its own, so the row borrows the D-pad while it is
; being edited. A gets in and out. TetrisGYM gives the seed row the same
; treatment (seedControls in gametypemenu/menu.asm); it can leave Up and Down
; free for the list because its list scrolls under a throttle and ours does not.
	ld   a, [wLabSeedDigit]
	cp   SEED_IDLE
	jp   nz, .editingSeed           ; jp: the CRUNCH row put this out of jr range

	bit  PADB_START, c
	jr   nz, .confirm
	bit  PADB_A, c
	jr   nz, .confirm

	bit  PADB_DOWN, c
	jr   z, .notDown
	ld   a, [wLabMode]
	inc  a
	cp   MODE_COUNT
	jr   c, .setRow
	xor  a
	jr   .setRow

.notDown:
	bit  PADB_UP, c
	jr   z, .notUp
	ld   a, [wLabMode]
	and  a
	jr   nz, .decRow
	ld   a, MODE_COUNT
.decRow:
	dec  a
	jr   .setRow

.notUp:
	ld   a, c
	and  PADF_LEFT | PADF_RIGHT
	ret  z
	ld   b, 1
	bit  PADB_RIGHT, c
	jr   nz, .haveDelta
	ld   b, -1
.haveDelta:
	ld   a, [wLabMode]
	cp   MODE_MUSIC
	jr   z, .adjustMusic
	cp   MODE_CRUNCH
	jr   z, .adjustCrunch
	cp   MODE_TRANSITION
	ret  nz

; the score the drill starts you on, in hundreds of thousands. 0-9 then A-F.
	ld   a, [wLabDrillScore]
	add  b
	cp   DRILL_SCORE_MAX + 1
	jr   c, .storeScore
	and  a                          ; wrapped past 0 or past F
	ld   a, DRILL_SCORE_MAX
	jr   nz, .storeScore
	xor  a
.storeScore:
	ld   [wLabDrillScore], a
	jp   LabMenuSound


; TetrisGYM's own value, so a number means the same shape on both ROMs.
.adjustCrunch:
	ld   a, [wLabCrunch]
	add  b
	and  CRUNCH_MAX                 ; 0-F, wrapping at both ends
	ld   [wLabCrunch], a
	jp   LabMenuSound

.adjustMusic:
	ldh  a, [hMusicType]
	sub  MUSIC_TYPES_START
	add  b
	and  $03                        ; four options, wrapping
	add  MUSIC_TYPES_START
	ldh  [hMusicType], a
	call PlaySongBasedOnMusicTypeChosen
	jp   LabMenuSound

.setRow:
	ld   [wLabMode], a
	jp   LabMenuSound

; Start or A. On a mode it launches; on the seed it opens the digits; on any
; other setting it does nothing, the split TetrisGYM draws at MODE_GAME_QUANTITY.
.confirm:
	ld   a, [wLabMode]
	cp   MODE_SEED
	jr   z, .editSeed
	cp   MODE_LAUNCHABLE
	ret  nc
	jp   LabMenuLaunch

.editSeed:
	xor  a
	ld   [wLabSeedDigit], a
	jp   LabMenuSound

; --- the seed row has the D-pad ---
.editingSeed:
	ld   d, a                       ; d = digit index

	bit  PADB_START, c
	jr   nz, .leaveSeed
	bit  PADB_A, c
	jr   nz, .leaveSeed

	bit  PADB_UP, c
	jr   z, .seedNotUp
	ld   b, 1
	jr   .seedAdjust
.seedNotUp:
	bit  PADB_DOWN, c
	jr   z, .seedNotDown
	ld   b, -1
.seedAdjust:
	ld   a, d
	ld   c, a
	call LabAdjustSeedNibble
	jp   LabMenuSound

.seedNotDown:
	bit  PADB_RIGHT, c
	jr   z, .seedNotRight
	ld   a, d
	cp   SEED_DIGITS - 1
	ret  nc
	inc  a
	ld   [wLabSeedDigit], a
	jp   LabMenuSound

.seedNotRight:
	bit  PADB_LEFT, c
	ret  z
	ld   a, d
	and  a
	jr   z, .leaveSeed              ; Left off the first digit leaves the row
	dec  a
	ld   [wLabSeedDigit], a
	jp   LabMenuSound

.leaveSeed:
	ld   a, SEED_IDLE
	ld   [wLabSeedDigit], a
	jp   LabMenuSound


; Start on a mode. Each hands over to its type's level select, the way the
; original screen did - the level comes from there and nowhere else.
LabMenuLaunch::
	ld   a, SND_CONFIRM_OR_LETTER_TYPED
	ld   [wSquareSoundToPlay], a

	ld   a, [wLabMode]
	cp   MODE_BTYPE
	jr   z, .bType
	cp   MODE_TRANSITION
	jr   z, .transition
	cp   MODE_CRUNCH
	jr   z, .transition             ; same handover: A-type, level from the picker

	ld   a, GAME_TYPE_A_TYPE
	ldh  [hGameType], a
	ld   a, GS_A_TYPE_SELECTION_INIT
	ldh  [hGameState], a
	ret

.bType:
	ld   a, GAME_TYPE_B_TYPE
	ldh  [hGameType], a
	ld   a, GS_B_TYPE_SELECTION_INIT
	ldh  [hGameState], a
	ret

; TRANSITION starts like TETRIS does: the level comes from the level select and
; nowhere else. The row's value is the trainer's own parameter.
.transition:
	ld   a, GAME_TYPE_A_TYPE
	ldh  [hGameType], a
	ld   a, GS_A_TYPE_SELECTION_INIT
	ldh  [hGameState], a
	ret

LabMenuSound::
	ld   a, SND_MOVING_SELECTION
	ld   [wSquareSoundToPlay], a
	ret


; The one-off paint, with the LCD off - the labels never change afterwards.
LabMenuDraw::
	ld   b, BANK(LabLoadGfx)
	ld   hl, LabLoadGfx
	call FarCall                    ; LCD off, then the menu tileset
	call LabPutCursorTile
	call Clear_wOam

	ld   de, LabMenuScreen
	call CopyLayoutToScreen0

	ld   hl, LabMenuTitle
	ld   de, _SCRN0 + 2 * 32 + 3
	call LabMenuPutString

	ld   hl, LabMenuLabels
	ld   de, MENU_ROW0 + MENU_TEXT_COL
	ld   b, MODE_COUNT
.nextLabel:
	push bc
	push de
	call LabMenuPutString
	pop  de
	ld   a, e
	add  LOW(MENU_STRIDE)
	ld   e, a
	jr   nc, .noCarry
	inc  d
.noCarry:
	pop  bc
	dec  b
	jr   nz, .nextLabel

	call LabMenuPaint

	ld   a, LCDCF_ON|LCDCF_WIN9C00|LCDCF_BG8000|LCDCF_OBJON|LCDCF_BGON
	ldh  [rLCDC], a
	ret


; Everything that changes: the cursor cells and the row values. Every write goes
; through LabPutTile, which waits for the LCD - dropped writes are what made the
; cursor vanish at random and left the music letter stale.
LabMenuRepaint::
	ld   hl, wLabBlinkTimer
	inc  [hl]

LabMenuPaint::
	ld   de, MENU_ROW0
	ld   b, 0

.nextRow:
	ld   a, [wLabMode]
	cp   b
	ld   a, MENU_CURSOR
	jr   z, .putCursor
	ld   a, TILE_BLANK
.putCursor:
	ld   h, d
	ld   l, e
	call LabPutTile

; the value, if the row has one
	ld   a, b
	cp   MODE_TRANSITION
	call z, LabMenuPaintLevel
	ld   a, b
	cp   MODE_CRUNCH
	call z, LabMenuPaintCrunch
	ld   a, b
	cp   MODE_SEED
	call z, LabMenuPaintSeed
	ld   a, b
	cp   MODE_MUSIC
	call z, LabMenuPaintMusic

	ld   hl, MENU_STRIDE
	add  hl, de
	ld   d, h
	ld   e, l
	inc  b
	ld   a, b
	cp   MODE_COUNT
	jr   c, .nextRow
	ret


; DE = row base. Returns HL at the row's value column.
LabMenuValueCell::
	ld   hl, MENU_VALUE_COL
	add  hl, de
	ret


; The seed row's first digit cell - two columns left of every other row's value,
; because six digits do not fit where four did.
LabMenuSeedCell::
	ld   hl, MENU_SEED_COL
	add  hl, de
	ret


; 0-9 then A-F: the font puts those tiles at $00-$0F, so the tile is the value.
LabMenuPaintLevel::
	call LabMenuValueCell
	ld   a, [wLabDrillScore]
	jp   LabPutTile


; 0-F, and the font puts those tiles at $00-$0F, so the tile is the value.
LabMenuPaintCrunch::
	call LabMenuValueCell
	ld   a, [wLabCrunch]
	jp   LabPutTile


; Four hex digits; the tile is the nibble. The digit being edited blinks.
LabMenuPaintSeed::
	call LabMenuSeedCell
	push de
	ld   d, h
	ld   e, l
	ld   c, 0
.digit:
	push de
	call LabReadSeedNibble
	push af
	ld   a, [wLabSeedDigit]
	cp   c
	jr   nz, .draw
	ld   a, [wLabBlinkTimer]
	and  $10
	jr   nz, .draw
	pop  af
	ld   a, TILE_BLANK
	jr   .store
.draw:
	pop  af
.store:
	pop  de
	ld   h, d
	ld   l, e
	call LabPutTile
	inc  de
	inc  c
	ld   a, c
	cp   SEED_DIGITS
	jr   c, .digit
	pop  de
	ret


; The music letter. OFF is drawn as a dash.
LabMenuPaintMusic::
	call LabMenuValueCell
	ldh  a, [hMusicType]
	cp   MUSIC_TYPE_OFF
	ld   a, $25                     ; "-"
	jr   z, .put
	ldh  a, [hMusicType]
	sub  MUSIC_TYPES_START
	add  $0a                        ; "A"
.put:
	jp   LabPutTile


; hl = zero-terminated string, de = tilemap destination.
; Where the original writes A-TYPE, at row 1 of the level select.
DEF MODE_LABEL_CELL EQU _SCRN0 + 1 * 32 + 2


; The level select says A-TYPE because that is what the original's layout says,
; and for TETRIS that is right. For a trainer it is not: the screen you are
; setting up is CRUNCH's, and nothing on it said so.
;
; Only the trainers. TETRIS keeps A-TYPE, and B-TYPE has its own screen the Lab
; does not hook at all. The original's init repaints the layout on the way in,
; so this only has to be written once and never restored.
LabPaintModeLabel::
	ld   a, [wLabMode]
	cp   MODE_TRANSITION
	ret  c                          ; TETRIS: A-TYPE is the right word
	cp   MODE_LAUNCHABLE
	ret  nc                         ; settings never reach a level select

	call LabModeLabel
	ld   hl, MODE_LABEL_CELL
	call LabPutStringLCDSafe

; And a blank after it. The layout sets A-TYPE off with one either side, and a
; six-letter name inherits the right-hand one; a ten-letter name runs past it
; and would meet the frame's dots with nothing between. The writer leaves hl on
; the cell after the name, which is exactly the one to clear.
	ld   a, TILE_BLANK
	jp   LabPutTile


; de = a zero-terminated string, hl = where it goes. Every cell through
; LabPutTile: this screen is painted with the LCD on, and a bare write is
; dropped while a line is being drawn.
LabPutStringLCDSafe::
	ld   a, [de]
	and  a
	ret  z
	inc  de
	call LabPutTile                 ; keeps de and hl; clobbers a and b
	inc  hl
	jr   LabPutStringLCDSafe


; a = a mode. Returns de = its label, by walking the labels the menu draws -
; one zero-terminated string per row, in wLabMode order, so the row's name and
; the level select's are the same string and cannot drift apart.
LabModeLabel::
	ld   de, LabMenuLabels
	and  a
	ret  z
	ld   b, a

.skipOne:
	ld   a, [de]
	inc  de
	and  a
	jr   nz, .skipOne
	dec  b
	jr   nz, .skipOne
	ret


LabMenuPutString::
	ld   a, [hl+]
	and  a
	ret  z
	ld   [de], a
	inc  de
	jr   LabMenuPutString


; The menu's static background: 20x18, the shape every original screen uses, so
; the original's own CopyLayoutToScreen0 paints it. Designed in TREP.
LabMenuScreen::
	INCBIN "src/lab/data/labMenuScreen.bin"


PUSHC
SETCHARMAP labfont
LabMenuTitle::
	db "TETRIS LAB GB", 0

; One zero-terminated label per row, in wLabMode order.
LabMenuLabels::
	db "TETRIS", 0
	db "B-TYPE", 0
	db "TRANSITION", 0
	db "CRUNCH", 0
	db "SEED", 0
	db "MUSIC", 0
POPC
