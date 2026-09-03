; --------------------------------------------------------------------------
; The Lab menu
;
; Tolstoj's design, from the proof of concept he sent on 2026-09-02: one list
; taller than the screen, grouped under STANDARD / COMPETITION / TRAINING
; headers, scrolling under the cursor once the selection passes the middle. The
; layout is his, drawn in TREP - 20 columns by 32 rows, which is exactly the
; height of the background map, so the whole list is drawn once and scrolled
; rather than repainted.
;
; It stays on $08/$0E, the game type screen's own states, rather than replacing
; the title screen the way his POC does. The title screen is where 1 PLAYER /
; 2 PLAYER is chosen, and SerialFunc0_titleScreen ($0078) assigns a link role
; only while hGameState is $07 - so ADR 0007 stands, and link play is one press
; from the boot screen rather than a row inside a twelve-row list.
; --------------------------------------------------------------------------

DEF MENU_MAP_ROWS    EQU 32          ; the layout is the whole background map
DEF MENU_ANCHOR_ROW  EQU 15          ; the visible row the selection sits on
                                     ; once the list has started scrolling
DEF MENU_CURSOR_X    EQU $10        ; already an OAM coordinate: OAM X is the
                                    ; screen column plus 8, so this is column 1
DEF MENU_CURSOR_COL  EQU 1
DEF MENU_DAS_FIRST   EQU 24          ; his values, so the menu feels like his
DEF MENU_DAS_REPEAT  EQU 8

; The selected row's value blinks, and only the value - the labels stay put.
; Bright copies of the font are made at init by keeping one bitplane of each
; glyph and clearing the other, which turns the darkest shade into the light
; one. Tolstoj's trick, and it costs no artwork: the bright alphabet is the
; normal alphabet, one plane lighter.
;
; The font is 0-9, A-Z, a dot and a dash, contiguous from $00, so one offset
; reaches every bright glyph. The layout tops out at $9B and the cursor is $FF,
; so $A0 upward is free.
; Where his sheet lands, matching the title screen's: the first tile after the
; font. Its last seven tiles run under the bright alphabet below, and the layout
; does not reach them.
DEF MENU_TILE_FIRST  EQU $27
DEF MENU_TILE_COUNT  EQU 128

; The selected row's value blinks, and only the value - the labels stay put.
; See LAB_BRIGHT in dispatch.asm for how the light alphabet is made.
DEF MENU_BLINK_MASK  EQU $10        ; 16 frames lit, 16 dark

; One entry per row of the list: the map row it is drawn on, and the mode it
; selects. The map carries the labels and the section headers, so this table is
; only what the cursor can land on - which is what makes a row that is drawn
; but has nothing behind it yet a matter of leaving it out.
DEF MENU_ROW_SIZEOF  EQU 2

LabMenuEntries::
	db  8, MODE_MUSIC
	db 14, MODE_TETRIS
	db 15, MODE_BTYPE
	db 19, MODE_SEED
	db 24, MODE_TRANSITION
	db 25, MODE_CRUNCH
	db 26, MODE_OBSTACLE
DEF MENU_ENTRIES     EQU 7

; The rows his layout draws that nothing exists behind yet. Blanked at init
; rather than left on screen: a row you can see and cannot reach reads as
; broken. Each becomes a table entry above and one deleted line here on the day
; it works.
LabMenuUnbuiltRows::
	db  9                            ; HZ-DISPLAY
	db 10                            ; INPUTS
	db 20                            ; LINE CAP
	db 27                            ; ELEVATED
	db $ff


; a = entry index. Returns d = its map row, e = its mode.
LabMenuEntry::
	add  a
	ld   e, a
	ld   d, 0
	ld   hl, LabMenuEntries
	add  hl, de
	ld   d, [hl]
	inc  hl
	ld   e, [hl]
	ret


; The mode the cursor is on, into wLabMode, so everything downstream of the menu
; still reads one byte and does not care that the list has grown headers and
; settings rows between the modes.
LabMenuSyncMode::
	ld   a, [wLabMenuRow]
	call LabMenuEntry
	ld   a, e
	ld   [wLabMode], a
	ret

; The menu screen is painted by the init state and nowhere else, the way every
; original screen works.
LabMenu::
	call LabMenuInput

; Nothing more once a row has launched. The screen has been blanked and its
; tileset handed back, and repainting would put this menu's values back onto it
; in the next screen's alphabet - which is most of what the flash on the way out
; was.
	ldh  a, [hGameState]
	cp   GS_GAME_TYPE_MAIN
	ret  nz

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
	jp   nz, .confirm               ; jp: the OBSTACLE row put this out of jr range
	bit  PADB_A, c
	jp   nz, .confirm

; Up and Down walk the entry table, not the map: the rows between the entries
; are the section headers, and the cursor steps over them. Auto-repeat is his,
; 24 frames then every 8, because a list this long is unusable without it.
	call LabMenuVerticalStep
	jr   nz, .moved
	jr   .notUp

.moved:
	ld   b, a                       ; +1 or -1
	ld   a, [wLabMenuRow]
	add  b
; Off an end: which end is bit 7, because stepping below zero leaves $FF and
; stepping past the top leaves MENU_ENTRIES.
	cp   MENU_ENTRIES
	jr   c, .setRow
	bit  7, a
	ld   a, 0
	jr   z, .setRow
	ld   a, MENU_ENTRIES - 1
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
	cp   MODE_OBSTACLE
	jr   z, .adjustObstacle
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

; Left and Right walk the height, and the wall comes with it: past the tallest
; left column is the shortest right one. TetrisGYM's own value order, so a
; number still means the same shape on both ROMs - and the two heights per side
; that no bar can cross are stepped over rather than offered, which is what the
; jump from $0E to $11 is.
.adjustObstacle:
	ld   a, [wLabObstacle]
	add  b
	cp   OBSTACLE_HEIGHT_MAX + 1
	jr   nz, .notPastTheLeftWall
	ld   a, OBSTACLE_RIGHT
	jr   .storeObstacle

.notPastTheLeftWall:
	cp   OBSTACLE_RIGHT - 1
	jr   nz, .notUnderTheRightWall
	ld   a, OBSTACLE_HEIGHT_MAX

.notUnderTheRightWall:
	cp   OBSTACLE_MAX + 1
	jr   c, .storeObstacle
	bit  7, a
	ld   a, OBSTACLE_MAX
	jr   nz, .storeObstacle
	xor  a

.storeObstacle:
	ld   [wLabObstacle], a
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
	ld   [wLabMenuRow], a
	call LabMenuSyncMode
	call LabMenuScroll
	call LabMenuCursor
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
	cp   MODE_OBSTACLE
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

LabMenuSound::
	ld   a, SND_MOVING_SELECTION
	ld   [wSquareSoundToPlay], a
	ret


; The one-off paint, with the LCD off. The whole 32-row map goes down once and
; is scrolled afterwards, so nothing here runs again.
LabMenuDraw::
	ld   b, BANK(LabLoadGfx)
	ld   hl, LabLoadGfx
	call FarCall                    ; LCD off, then the menu tileset
	call LabPutCursorTile

; Tolstoj's sheet over the top of the original's, the way the title screen does
; it. The layout is drawn against these tiles: the letters are the same in every
; tileset, so a menu without them reads correctly and is drawn entirely in the
; wrong furniture - the box, the frame and the section rules all come from here.
	ld   hl, LabMenuTiles
	ld   de, _VRAM + MENU_TILE_FIRST * 16
	ld   bc, MENU_TILE_COUNT * 16
.copyTiles:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  bc
	ld   a, b
	or   c
	jr   nz, .copyTiles

	call LabMakeBrightFont          ; after the sheet, which reaches into $A0
	call Clear_wOam

; The twelve columns the layout does not cover are still whatever the last
; screen left there, and they scroll into view with everything else.
	call LabMenuClearMap

	ld   de, LabMenuMap
	ld   hl, _SCRN0
	ld   b, MENU_MAP_ROWS
	call CopyLayoutBrowsToHL

	call LabMenuBlankUnbuilt
	call LabMenuBlankBakedCursors

; The cursor stays where it was. Coming back from a level select should find
; the row you launched from, scrolled the way you left it - the loop is "set it
; up, try it, come back and change it", and starting from the top every time
; makes the list's own length the price of that. wLabMenuRow survives in WRAM;
; a cold boot zeroes it, which is the first row.
	xor  a
	ld   [wLabMenuDas], a

	ld   a, [wLabMenuRow]
	cp   MENU_ENTRIES
	jr   c, .haveRow
	xor  a                          ; out of range: the list must have shrunk
	ld   [wLabMenuRow], a

.haveRow:
	call LabMenuSyncMode

; The scroll to match, written straight out: the LCD is off, so there is nothing
; to tear, and LabMenuScroll's wait for VBlank would never end.
	call LabMenuScrollForRow
	ld   [wLabMenuScroll], a
	ldh  [rSCY], a

	call LabMenuPaint
	call LabMenuCursor

	ld   a, LCDCF_ON|LCDCF_WIN9C00|LCDCF_BG8000|LCDCF_OBJON|LCDCF_BGON
	ldh  [rLCDC], a
	ret


; The whole background map, not the visible window: the list is 32 rows tall and
; the columns past the layout's 20 scroll into view with it.
LabMenuClearMap::
	ld   hl, _SCRN0
	ld   de, MENU_MAP_ROWS * GB_TILE_WIDTH
	ld   a, TILE_EMPTY

.next:
	ld   [hl+], a
	dec  de
	ld   b, a
	ld   a, d
	or   e
	ld   a, b
	jr   nz, .next
	ret


; The rows nothing exists behind yet, wiped between the box's own sides.
LabMenuBlankUnbuilt::
	ld   hl, LabMenuUnbuiltRows
.nextRow:
	ld   a, [hl+]
	cp   $ff
	ret  z
	push hl
	call LabMenuRowAddress
	ld   b, SCREEN_TILE_WIDTH - 2
	ld   a, TILE_EMPTY
.nextCell:
	inc  hl
	ld   [hl], a
	dec  b
	jr   nz, .nextCell
	pop  hl
	jr   .nextRow


; a = tile. The same, shifted into the bright alphabet while the row being
; painted is the selected one and the blink is on its lit half.
;
; Glyphs only. The bright block is a copy of the font and stops where the font
; does, so shifting anything else lands on whatever tile happens to sit there -
; MUSIC pads "OFF" out to six cells with blanks, and each of those blinked into
; a different piece of the artwork. Reported by Giovanni.
LabMenuPutValue::
	cp   LAB_FONT_TILES
	jp   nc, LabPutTile             ; not a glyph: nothing to brighten

	push bc
	ld   b, a
	ld   a, [wLabMenuBright]
	add  b
	pop  bc
	jp   LabPutTile


; Tolstoj draws the cursor into his layouts - it is how the title screen marks
; 1 PLAYER, where the artwork's own arrow moves and there is no sprite at all.
; Here it sits at the MUSIC row and cannot move, because the list scrolls under
; the cursor and a cell in the map scrolls with the list. So the sprite is the
; cursor and the drawn ones come out, or the screen shows two arrows and only
; one of them means anything. The title screen had exactly this bug.
;
; Every entry's cursor column, not just the one he drew, so a re-cut layout
; cannot quietly bring it back.
LabMenuBlankBakedCursors::
	ld   b, 0

.nextEntry:
	push bc
	ld   a, b
	call LabMenuEntry
	ld   a, d
	call LabMenuRowAddress
	ld   de, MENU_CURSOR_COL
	add  hl, de
	ld   [hl], TILE_EMPTY
	pop  bc
	inc  b
	ld   a, b
	cp   MENU_ENTRIES
	jr   c, .nextEntry
	ret


; a = a map row. Returns hl = its first cell in the background map.
LabMenuRowAddress::
	ld   h, 0
	ld   l, a
	add  hl, hl
	add  hl, hl
	add  hl, hl
	add  hl, hl
	add  hl, hl                     ; * GB_TILE_WIDTH
	ld   de, _SCRN0
	add  hl, de
	ret


; Everything that changes: the cursor cells and the row values. Every write goes
; through LabPutTile, which waits for the LCD - dropped writes are what made the
; cursor vanish at random and left the music letter stale.
LabMenuRepaint::
	ld   hl, wLabBlinkTimer
	inc  [hl]

LabMenuPaint::
	ld   b, 0

.nextEntry:
	push bc
	ld   a, b
	call LabMenuEntry
	ld   c, e                       ; this entry's mode, not the selected one
	ld   a, d
	call LabMenuRowAddress
	ld   d, h
	ld   e, l                       ; de = the row, in the map

; Bright while this is the row the cursor is on and the blink is lit. Every
; other row is painted dark, which is what puts a value back to black when the
; cursor leaves it - no restoring, just the next frame.
	push bc
	ld   b, 0
	ld   a, [wLabMode]
	cp   c
	jr   nz, .haveBright
	ld   a, [wLabBlinkTimer]
	and  MENU_BLINK_MASK
	jr   z, .haveBright
	ld   b, LAB_BRIGHT
.haveBright:
	ld   a, b
	ld   [wLabMenuBright], a
	pop  bc

	ld   a, c
	cp   MODE_TRANSITION
	call z, LabMenuPaintLevel
	ld   a, c
	cp   MODE_CRUNCH
	call z, LabMenuPaintCrunch
	ld   a, c
	cp   MODE_OBSTACLE
	call z, LabMenuPaintObstacle
	ld   a, c
	cp   MODE_SEED
	call z, LabMenuPaintSeed
	ld   a, c
	cp   MODE_MUSIC
	call z, LabMenuPaintMusic

	pop  bc
	inc  b
	ld   a, b
	cp   MENU_ENTRIES
	jr   c, .nextEntry
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
	jp   LabMenuPutValue


; 0-F, and the font puts those tiles at $00-$0F, so the tile is the value.
LabMenuPaintCrunch::
	call LabMenuValueCell
	ld   a, [wLabCrunch]
	jp   LabMenuPutValue


; The height, then the wall it stands against.
;
; The value is TetrisGYM's, one cell, so a number means the same shape on both
; ROMs - but their encoding hides the side inside it, and Tolstoj's layout gives
; the row a letter for it. Painting that letter is what makes the two agree:
; the layout has "L" baked in, so a right-wall value read as a left-wall one
; until this drew over it.
;
; The font runs 0-9 then A-Z from $00, so a height is its own tile.
DEF MENU_OBSTACLE_SIDE EQU 2         ; cells right of the value
DEF TILE_L             EQU $15
DEF TILE_R             EQU $1b

LabMenuPaintObstacle:
	push bc
	call LabMenuValueCell

; The height, which is the value on the left wall and the value less $10 on the
; right. Shown rather than the raw number because the raw number beside a side
; letter contradicts it: $18 is the right wall eight rows tall, and "O R" reads
; as neither.
	call LabObstacleHeight
	call LabMenuPutValue

	ld   bc, MENU_OBSTACLE_SIDE
	add  hl, bc

; The wall, always shown and never blinking. Only the number is being changed,
; so only the number should flash - and a row whose only mark is a nought reads
; as broken, which is why Tolstoj's layout draws "0 L" rather than a bare zero.
	call LabObstacleOnLeft
	ld   a, TILE_L
	jr   c, .put
	ld   a, TILE_R

.put:
	call LabPutTile
	pop  bc
	ret


; Four hex digits; the tile is the nibble. The digit being edited blinks.
; BC is the paint loop's entry counter and the mode it is dispatching on, and
; this is the one painter that needs C for itself - it left C holding six, which
; is MODE_MUSIC, so the music painter ran on the seed row and drew "B-TYPE" over
; the digits.
LabMenuPaintSeed::
	push bc
	call LabMenuSeedCell
	push de
	ld   d, h
	ld   e, l
	ld   c, 0

.digit:
	call LabMenuSeedBright          ; b = this digit's tile offset
	push de
	call LabReadSeedNibble
	add  b
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
	pop  bc
	ret


; c = a digit index. Returns b = the tile offset to draw it with.
;
; While the row is being edited only the digit under the cursor blinks, and the
; rest stay dark whatever the row-level blink is doing - otherwise the whole
; value pulses and the one you are changing is lost in it. Idle, the digits
; follow the row.
LabMenuSeedBright::
	ld   a, [wLabSeedDigit]
	cp   SEED_IDLE
	jr   z, .followTheRow

	ld   b, 0
	cp   c
	ret  nz                         ; some other digit: dark
	ld   a, [wLabBlinkTimer]
	and  MENU_BLINK_MASK
	ret  z
	ld   b, LAB_BRIGHT
	ret

.followTheRow:
	ld   a, [wLabMenuBright]
	ld   b, a
	ret




; The music, spelled out. Six cells, because the layout gives the row six and a
; single letter beside a baked "-TYPE" is only right by accident - it read
; "--TYPE" with the music off.
DEF MENU_MUSIC_LEN EQU 6

LabMenuPaintMusic::
	call LabMenuValueCell
	push hl

	ldh  a, [hMusicType]
	cp   MUSIC_TYPE_OFF
	ld   de, LabMenuMusicOff
	jr   z, .haveName

	sub  MUSIC_TYPES_START
	ld   e, a
	ld   d, 0
	ld   hl, LabMenuMusicNames
	add  hl, de
	add  hl, de
	add  hl, de
	add  hl, de
	add  hl, de
	add  hl, de                     ; * MENU_MUSIC_LEN
	ld   d, h
	ld   e, l

.haveName:
	pop  hl
	ld   b, MENU_MUSIC_LEN
.nextCell:
	ld   a, [de]
	inc  de
	push bc
	call LabMenuPutValue
	pop  bc
	inc  hl
	dec  b
	jr   nz, .nextCell
	ret


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


PUSHC
SETCHARMAP labfont
LabMenuLabels::
	db "TETRIS", 0
	db "B-TYPE", 0
	db "TRANSITION", 0
	db "CRUNCH", 0
	db "OBSTACLE", 0
	db "SEED", 0
	db "MUSIC", 0
POPC


; --------------------------------------------------------------------------
; Walking the list
; --------------------------------------------------------------------------

; Z when nothing is due this frame; otherwise a = +1 for Down, -1 for Up.
;
; A fresh press acts at once and reloads the counter; holding waits
; MENU_DAS_FIRST frames and then repeats every MENU_DAS_REPEAT. One counter,
; because Up and Down cannot both be held to any useful effect.
LabMenuVerticalStep::
	ldh  a, [hButtonsPressed]
	and  PADF_UP | PADF_DOWN
	jr   z, .notFresh

	ld   b, a
	ld   a, MENU_DAS_FIRST
	ld   [wLabMenuDas], a
	jr   .step

.notFresh:
	ldh  a, [hButtonsHeld]
	and  PADF_UP | PADF_DOWN
	jr   z, .idle
	cp   PADF_UP | PADF_DOWN
	jr   z, .idle                   ; both down: neither wins

	ld   b, a
	ld   a, [wLabMenuDas]
	dec  a
	ld   [wLabMenuDas], a
	jr   z, .repeat
	xor  a
	ret                             ; still counting

.repeat:
	ld   a, MENU_DAS_REPEAT
	ld   [wLabMenuDas], a

.step:
	ld   a, b
	and  PADF_DOWN
	jr   z, .stepUp
	ld   a, 1
	and  a                          ; Z clear
	ret

.stepUp:
	ld   a, -1
	and  a                          ; $ff, so Z is clear
	ret

.idle:
	xor  a
	ld   [wLabMenuDas], a
	ret                             ; Z set


; The view follows the selection: nothing scrolls while it is in the top half
; of the map, and below that the selected row is pinned to MENU_ANCHOR_ROW.
;
; Written in VBlank. SCY takes effect the moment it is written, so setting it
; mid-frame tears the picture across whichever line the beam is on.
LabMenuScroll::
	call LabMenuScrollForRow
	ld   b, a
	ld   a, [wLabMenuScroll]
	cp   b
	ret  z
	ld   a, b
	ld   [wLabMenuScroll], a

.waitVBlank:
	ldh  a, [rLY]
	cp   SCRN_Y
	jr   c, .waitVBlank
	ld   a, [wLabMenuScroll]
	ldh  [rSCY], a
	ret


; a = where the map has to sit for the selected row to be visible. Nothing while
; the row is in the top half; below that the row is pinned to MENU_ANCHOR_ROW
; and the map moves instead.
LabMenuScrollForRow::
	ld   a, [wLabMenuRow]
	call LabMenuEntry
	ld   a, d                       ; the map row
	sub  MENU_ANCHOR_ROW
	jr   nc, .below
	xor  a                          ; still in the top half: no scroll
	ret

.below:
	add  a
	add  a
	add  a                          ; rows -> pixels
	ret


; The arrow, as a sprite. A background cursor would have to be erased and
; redrawn on every move, and would scroll with the list rather than sit on it.
LabMenuCursor::
	ld   a, [wLabMenuRow]
	call LabMenuEntry
	ld   a, d
	add  a
	add  a
	add  a                          ; the map row, in pixels
	ld   b, a
	ld   a, [wLabMenuScroll]
	ld   c, a
	ld   a, b
	sub  c                          ; where it is on screen
	add  16                         ; OAM counts from off the top edge

	ld   hl, wOam
	ld   [hl+], a
	ld   a, MENU_CURSOR_X
	ld   [hl+], a
	ld   a, MENU_CURSOR
	ld   [hl+], a
	xor  a
	ld   [hl], a
	ret


; A-TYPE, B-TYPE, C-TYPE and OFF, padded to the six cells the row gives them.
PUSHC
SETCHARMAP labfont
LabMenuMusicNames::
	db "A-TYPE"
	db "B-TYPE"
	db "C-TYPE"
LabMenuMusicOff::
	db "OFF   "
POPC


LabMenuMap::
	INCBIN "src/lab/data/labMenuMap.bin"

LabMenuTiles::
	INCBIN "build/obj/build/labMenuTiles.2bpp"
