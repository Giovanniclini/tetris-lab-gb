; --------------------------------------------------------------------------
; The Lab menu
;
; The title screen, replaced. One scrolling-list-shaped menu of modes and
; settings, modelled on TetrisGYM's game type menu (ADR 0007). Also the link
; handshake, because 2 PLAYER is a row on it.
; --------------------------------------------------------------------------

; The menu screen is painted by the init state and nowhere else, the way every
; original screen works. $07 is only ever reached through $06 - including when
; SerialFunc0_titleScreen bounces a stray serial byte back there - so there is
; no first-entry case to handle.
LabMenu::
	call LabLinkPing
	ldh  a, [hGameState]
	cp   GS_TITLE_SCREEN_MAIN
	ret  nz                         ; a partner took over; stop touching the menu

	call LabMenuInput
	jp   LabMenuRepaint


; The title screen's own rendezvous, transcribed from GameState07_TitleScreenMain
; ($0488). A second Game Boy finds us by seeing this ping, so the menu has to
; keep sending it - and it has to do so from state $07, because
; SerialFunc0_titleScreen only assigns roles while hGameState says $07.
LabLinkPing::
	call SerialTransferWaitFunc
	ld   a, SB_PASSIVES_PING_IN_TITLE_SCREEN
	ldh  [rSB], a
	ld   a, SC_REQUEST_TRANSFER|SC_PASSIVE
	ldh  [rSC], a

	ldh  a, [hSerialInterruptHandled]
	and  a
	ret  z                          ; nothing arrived

	ldh  a, [hMultiplayerPlayerRole]
	and  a
	jp   nz, LabStart2Player        ; assigned a role: the master is waiting

	xor  a                          ; a byte, but no role - not a partner
	ldh  [hSerialInterruptHandled], a
	ret


LabStart2Player::
	xor  a
	ldh  [hTimer1], a
	ld   a, GS_2PLAYER_GAME_MUSIC_TYPE_INIT
	ldh  [hGameState], a
	ret


LabMenuInput::
	ldh  a, [hButtonsPressed]
	ld   c, a

; The seed needs a cursor of its own, so the row borrows the D-pad while it is
; being edited. A gets in and out. TetrisGYM gives the seed row the same
; treatment (seedControls in gametypemenu/menu.asm); it can leave Up and Down
; free for the list because its list scrolls under a throttle and ours does not.
	ld   a, [wLabSeedDigit]
	cp   SEED_IDLE
	jr   nz, .editingSeed

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
	ld   a, [wLabMode]
	cp   MODE_2PLAYER
	jr   z, .keepSerial
; What $08 did on the way into a one-player game ($1444): serial off, and the
; serial registers and any pending interrupt cleared. Leaving rIF holding a
; stale serial flag is what froze the first piece.
	ld   a, IEF_VBLANK
	ldh  [rIE], a
	xor  a
	ldh  [rSB], a
	ldh  [rSC], a
	ldh  [rIF], a
.keepSerial:
	ld   a, SND_CONFIRM_OR_LETTER_TYPED
	ld   [wSquareSoundToPlay], a

	ld   a, [wLabMode]
	cp   MODE_BTYPE
	jr   z, .bType
	cp   MODE_2PLAYER
	jr   z, .twoPlayer
	cp   MODE_TRANSITION
	jr   z, .transition

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

; The master half of the handshake, transcribed from $04BF. If a role is already
; assigned we are the master and the passive is waiting; otherwise announce
; ourselves and wait one transfer for an answer. With no cable the transfer
; still completes - the byte just comes back as $FF - so this cannot hang, and
; no role is assigned, and we stay on the menu.
.twoPlayer:
	ldh  a, [hMultiplayerPlayerRole]
	cp   MP_ROLE_MASTER
	jp   z, LabStart2Player

	ld   a, SB_MASTER_PRESSING_START
	ldh  [rSB], a
	ld   a, SC_REQUEST_TRANSFER|SC_MASTER
	ldh  [rSC], a

.waitForAnswer:
	ldh  a, [hSerialInterruptHandled]
	and  a
	jr   z, .waitForAnswer

	ldh  a, [hMultiplayerPlayerRole]
	and  a
	ret  z                          ; nobody answered: stay where we are
	jp   LabStart2Player


LabMenuSound::
	ld   a, SND_MOVING_SELECTION
	ld   [wSquareSoundToPlay], a
	ret


; The one-off paint, with the LCD off - the labels never change afterwards.
LabMenuDraw::
	ld   b, BANK(LabLoadMenuGfx)
	ld   hl, LabLoadMenuGfx
	call FarCall                    ; LCD off, then the menu tileset
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
	db "2 PLAYER", 0
	db "TRANSITION", 0
	db "SEED", 0
	db "MUSIC", 0
POPC
