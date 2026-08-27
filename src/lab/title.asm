; --------------------------------------------------------------------------
; The Lab title screen
;
; The original's screen on the original's states, with Tolstoj's artwork and
; the 1 PLAYER / 2 PLAYER choice the game always had.
;
; It has to be $06/$07 and no other pair. SerialFunc0_titleScreen ($0078)
; assigns a multiplayer role only while hGameState is $07, and forces every
; other state back to $06 - so this is where a link partner finds us, and
; being bounced here from the menu is the original's own behaviour rather than
; something to work around.
; --------------------------------------------------------------------------

; Where the artwork puts the version: the last three cells before the box's
; right edge, with the two before them left as the gap after "VERSION".
DEF VERSION_CELL    EQU _SCRN0 + 11 * 32 + 13
DEF VERSION_LEN     EQU 3

; The cursor is the artwork's own: Tolstoj drew an arrow into the layout beside
; 1 PLAYER, so selecting a side is moving that tile rather than putting a sprite
; over it. A sprite as well is two arrows, one of which does nothing.
DEF TITLE_ARROW     EQU $9c
DEF TITLE_BG        EQU $32
DEF TITLE_1P_CELL   EQU _SCRN0 + 15 * 32 + 0
DEF TITLE_2P_CELL   EQU _SCRN0 + 15 * 32 + 10

; Where Tolstoj's sheet lands: $27, the first tile after the font. Its first
; nine tiles reproduce the shared ones the menu's tileset puts there - the
; heart, the blocks, the frame - so his artwork proper starts at $30 and the
; run is contiguous from $27.
DEF TITLE_TILE_FIRST EQU $27
DEF TITLE_TILE_COUNT EQU 128


; Painted once, with the LCD off, the way every original screen is.
LabTitleDraw::
	ld   b, BANK(LabLoadGfx)
	ld   hl, LabLoadGfx
	call FarCall                    ; LCD off, then ascii + the title tileset

; Tolstoj's tiles over the top of the original's. The LCD is off, so a second
; pass over VRAM costs nothing, and it keeps the menu's tileset untouched -
; the menu reloads through the same thunk and finds $2F blank as it expects.
	ld   hl, LabTitleTiles
	ld   de, _VRAM + TITLE_TILE_FIRST * 16
	ld   bc, TITLE_TILE_COUNT * 16
.copyTiles:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  bc
	ld   a, b
	or   c
	jr   nz, .copyTiles

	call Clear_wOam

	ld   de, LabTitleScreen
	call CopyLayoutToScreen0

; The version, over the field the artwork leaves for it. Drawn rather than
; stored, so a release does not need a new layout - the digits and the dot are
; font tiles, which are loaded under every tileset.
	ld   hl, LabTitleVersion
	ld   de, VERSION_CELL
	ld   b, VERSION_LEN
.version:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  b
	jr   nz, .version

	call LabTitlePaint

	ld   a, LCDCF_ON|LCDCF_WIN9C00|LCDCF_BG8000|LCDCF_OBJON|LCDCF_BGON
	ldh  [rLCDC], a
	ret


; The arrow the original marks a selection with. It lives in the title-screen
; tileset, which the menu never loads, so the menu copies the one tile it needs
; into $FF. The title screen calls none of this - its cursor is the arrow
; Tolstoj drew into the artwork.
LabPutCursorTile::
	ld   hl, LabCursorTile
	ld   de, _VRAM + MENU_CURSOR * 16
	ld   b, 16
.next:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  b
	jr   nz, .next
	ret


LabCursorTile::
	INCBIN "build/obj/build/titleScreen.2bpp", (TILE_CURSOR - $27) * 16, 16


LabTitlePaint::
	ldh  a, [hIs2Player]
	and  a
	ld   a, TITLE_ARROW
	jr   z, .oneSelected
	ld   a, TITLE_BG
.oneSelected:
	ld   hl, TITLE_1P_CELL
	call LabPutTile

	ldh  a, [hIs2Player]
	and  a
	ld   a, TITLE_BG
	jr   z, .twoNotSelected
	ld   a, TITLE_ARROW
.twoNotSelected:
	ld   hl, TITLE_2P_CELL
	jp   LabPutTile


LabTitleMain::
	call LabLinkPing
	ldh  a, [hGameState]
	cp   GS_TITLE_SCREEN_MAIN
	ret  nz                         ; a partner took over; stop touching the screen

	call LabTitleInput
	jp   LabTitlePaint


LabTitleInput::
	ldh  a, [hButtonsPressed]
	ld   b, a
	ldh  a, [hIs2Player]

; How the original reads this screen ($04A7): Select flips between the two,
; Left and Right choose one, and a press for the side already chosen does
; nothing. Treating either direction as a flip means a double-tap of Right
; launches a one-player game and a double-tap of Left opens the link handshake.
	bit  PADB_SELECT, b
	jr   nz, .flip
	bit  PADB_RIGHT, b
	jr   nz, .pressedRight
	bit  PADB_LEFT, b
	jr   nz, .pressedLeft
	jr   .noMove

.pressedRight:
	and  a
	ret  nz                         ; already 2 PLAYER
	jr   .flip

.pressedLeft:
	and  a
	ret  z                          ; already 1 PLAYER

.flip:
	xor  $01
	ldh  [hIs2Player], a
	ld   a, SND_MOVING_SELECTION
	ld   [wSquareSoundToPlay], a
	ret

.noMove:
	ld   a, b
	and  PADF_START|PADF_A
	ret  z

	ld   a, SND_CONFIRM_OR_LETTER_TYPED
	ld   [wSquareSoundToPlay], a

	ldh  a, [hIs2Player]
	and  a
	jr   nz, LabTitle2Player

; One player: on to the Lab menu, which is where the game type is chosen now.
; What $08 did on the way into a one-player game ($1444): serial off, and the
; serial registers and any pending interrupt cleared. Leaving rIF holding a
; stale serial flag is what froze the first piece.
	ld   a, IEF_VBLANK
	ldh  [rIE], a
	xor  a
	ldh  [rSB], a
	ldh  [rSC], a
	ldh  [rIF], a

	ld   a, GS_GAME_MUSIC_TYPE_INIT
	ldh  [hGameState], a
	ret


; The master half of the handshake, transcribed from $04BF. If a role is already
; assigned we are the master and the passive is waiting; otherwise announce
; ourselves and wait one transfer for an answer. With no cable the transfer
; still completes - the byte just comes back as $FF - so this cannot hang, and
; no role is assigned, and we stay on the title screen.
LabTitle2Player::
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


; The title screen's own rendezvous, transcribed from GameState07_TitleScreenMain
; ($0488). A second Game Boy finds us by seeing this ping, so the screen has to
; keep sending it.
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


PUSHC
SETCHARMAP labfont
LabTitleVersion::
	db LAB_VERSION
POPC


; Tolstoj's title screen: the layout he designed, and the tiles it indexes.
LabTitleScreen::
	INCBIN "src/lab/data/labTitleScreen.bin"

LabTitleTiles::
	INCBIN "build/obj/build/labTitleScreen.2bpp"
