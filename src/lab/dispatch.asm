; --------------------------------------------------------------------------
; State dispatch
;
; Opens the bank 2 section every other module continues, so this include
; must come first.
;
; Reached from LabStateHook in bank 0 with bank 2 mapped. Each hooked game
; state arrives here, the Lab does its own work, and the address of the
; original handler goes back in HL for the caller to chain to. The handlers
; are local labels because the dispatch is the only thing that reaches them.
; --------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; Bank 2 - Lab core
; ---------------------------------------------------------------------------

SECTION "Lab Core", ROMX[$4000], BANK[2]

LabVersion::
	db "TETRISLABGB ", LAB_VERSION, 0

; Entry point for the Lab, reached via FarCall with b = BANK(LabInit).
; Does nothing yet: Milestone 0.5 expands the cartridge, it does not add
; behaviour. The trampoline and this stub exist so that Milestone 1 has
; somewhere to land.
LabInit::
	ret

; ---------------------------------------------------------------------------
; State dispatch
;
; Reached from LabStateHook in bank 0, with bank 2 mapped. Does the Lab's own
; work, then returns in HL the address of the original handler for the caller
; to chain to.
;
; This code must not call anything in $4000-$7FFF: while bank 2 is mapped that
; range is Lab code, not the original bank 1. Calls into bank 0 are fine, but
; only if the target does not itself reach into bank 1 - the original A-type
; init calls the sound engine, which does. So we touch RAM only, and let the
; original handler run afterwards with bank 1 restored.
; ---------------------------------------------------------------------------

LabDispatch::
	ldh  a, [hGameState]
	cp   GS_LEVEL_ENDED_MAIN
	jr   z, .levelEnded
	cp   GS_ENTERING_HIGH_SCORE
	jr   z, .nameEntry
	cp   GS_IN_GAME_INIT
	jr   z, .gameInit
	cp   GS_A_TYPE_SELECTION_INIT
	jr   z, .init
	cp   GS_TITLE_SCREEN_MAIN
	jp   z, .titleMain
	cp   GS_TITLE_SCREEN_INIT
	jp   z, .titleInit
	cp   GS_GAME_MUSIC_TYPE_INIT
	jp   z, .menuInit
	cp   GS_GAME_TYPE_MAIN
	jp   z, .menu
	cp   GS_IN_GAME_MAIN
	jp   z, .inGameMain
	cp   GS_COPYRIGHT_DISPLAY
	jr   z, .skipCopyright
	cp   GS_PRE_ROCKET_SCENE_WAIT
	jr   z, .skipRocket

; The original main handler only calls bank-0 routines, so we can run it
; ourselves and then correct what it did. Fixing up afterwards is the only way
; to move the cursor sprite, which the original repositions on its own terms.
	call LabLevelSelectMain
	call GameState11_ATypeSelectionMain
	call LabLevelSelectPost
	ld   hl, Stub_148c              ; the stub's `jp hl` must land somewhere
	ret

.init:
	call LabLevelSelectInit
	ld   hl, GameState10_ATypeSelectionInit
	ret

; The end-of-game screen. Its handler treats Start as "back to the level
; select", and Start is part of the reset combination - so by the time either
; soft-reset check runs, the state has already moved on and we would reboot.
; Catch the combination here instead, which is what makes "top out, go again"
; work.
.levelEnded:
	call LabResetComboHeld
	jr   nz, .runLevelEnded

	call LabInGameReset             ; state is GS_LEVEL_ENDED_MAIN: restarts
	ld   hl, Stub_148c
	ret

.runLevelEnded:
	ld   hl, GameState04_LevelEndedMain
	ret

; The rocket and its 2.4-second wait, skipped whole. This is the state the
; original goes to when the score earns a celebration; sending it to the plain
; game over screen is what it does for every score that does not.
.skipRocket:
	ld   a, GS_LEVEL_ENDED_MAIN
	ldh  [hGameState], a
	ld   hl, Stub_148c
	ret

; Typing a high score name. Restarting here abandons the score, which is the
; point: when you are drilling you want another go, not a leaderboard entry.
.nameEntry:
	call LabResetComboHeld
	jr   nz, .runNameEntry

	call LabInGameReset
	ld   hl, Stub_148c
	ret

.runNameEntry:
	call LabRedrawHiScoreMillions   ; the score is on screen while the name is typed
	ld   hl, GameState15_EnteringHighScore
	ret

; Every game begins here, whether from the menu or an instant restart, so this
; is the one place to load the configured seed into the LFSR. A restart must
; repeat the sequence, not continue it.
.gameInit:
	xor  a
	ld   [wLabScoreMillions], a     ; the original clears its three bytes here too
	ld   [wLabScoreCarryDrawn], a
	ld   [wLabScoreZeroMoved], a
	call LabArmSeed
	call LabArmDrill
	ld   hl, GameState0a_InGameInit
	ret

; The copyright screen: 8.5 seconds before the title, every boot. Its only
; lasting effect is copying DemoPieces into wDemoOrMultiplayerPieces, and the
; only thing that reads that is the attract demo - 2-player shuffles its own
; table into it at $068C. The Lab menu never runs a demo, so none of it is
; needed. The tile data comes from $06 either way.
.skipCopyright:
	ld   a, GS_TITLE_SCREEN_INIT
	ldh  [hGameState], a
	ld   hl, Stub_148c
	ret

; The title screen's init. The clears are the original's ($03AE), transcribed;
; the artwork and the cursor are ours.
;
; The screen buffer clear is not cosmetic. InGameCheckIfAnyTetrisRowsComplete
; ($213E) scans wGameScreenBuffer for TILE_EMPTY to decide which rows are full -
; leave it holding anything else and every row reads as complete the moment the
; first piece lands, which overruns a four-entry list and hangs the game.
.titleInit:
	xor  a
	ldh  [hIsRecordingDemo], a
	ldh  [hPieceFallingState], a
	ldh  [hTetrisFlashCount], a
	ldh  [hPieceCollisionDetected], a
	ldh  [h1stHighScoreHighestByteForLevel], a
	ldh  [hNumLinesCompletedBCD + 1], a
	ldh  [hRowsShiftingDownState], a
	ldh  [hMustEnterHighScore], a
	call ClearPointersToCompletedTetrisRows
	call ClearScoreCategoryVarsAndTotalScore

	ld   hl, wGameScreenBuffer
.clearScreenBuffer:
	ld   a, TILE_EMPTY
	ld   [hl+], a
	ld   a, h
	cp   HIGH(wGameScreenBuffer.end)
	jr   nz, .clearScreenBuffer

; The walls and the floor. Not decoration: the falling piece collides against
; what is in this buffer, so without them a piece falls past the bottom for
; ever and no game ever ends.
	ld   hl, wGameScreenBuffer + 1
	call DisplayBlackColumnFromHLdown
	ld   hl, wGameScreenBuffer + $c
	call DisplayBlackColumnFromHLdown

	ld   hl, wGameScreenBuffer + $241
	ld   b, $0c
	ld   a, TILE_BLACK
.displayBlackRow:
	ld   [hl+], a
	dec  b
	jr   nz, .displayBlackRow

; serial back on: the title screen is where a link partner finds us
	ld   a, IEF_VBLANK | IEF_SERIAL
	ldh  [rIE], a

	call LabTitleDraw

; Start the music the MUSIC row is set to. The screens this menu replaced each
; did their own: the title screen played MUS_TITLE_SCREEN, the A/B screen played
; the chosen type ($1481). The chosen type is right here - you audition it on
; the row - so that is the one to play. Without this the menu is silent until
; you nudge the row, which is what gave it away.
	ld   a, MUS_TITLE_SCREEN
	ld   [wSongToStart], a
	ld   a, GS_TITLE_SCREEN_MAIN
	ldh  [hGameState], a
	ld   hl, Stub_148c
	ret

.titleMain:
	call LabTitleMain
	ld   hl, Stub_148c
	ret

; The Lab menu, on the game type screen's own states - $08 paints it and $0E
; runs it, the pair the original used for A-TYPE/B-TYPE. B on a level select
; comes back to $08, which is where it came from.
.menuInit:
	ld   a, SEED_IDLE
	ld   [wLabSeedDigit], a
	call LabMenuDraw

; The song the MUSIC row is set to: this is the screen you audition it on.
	call PlaySongBasedOnMusicTypeChosen
	ld   a, GS_GAME_TYPE_MAIN
	ldh  [hGameState], a
	ld   hl, Stub_148c
	ret

.menu:
	call LabMenu
	ld   hl, Stub_148c
	ret

; Every gameplay frame. Anything a trainer must do after the original's in-game
; init has run belongs here: that init clears the line count and the score, so
; setting them beforehand achieves nothing.
.inGameMain:
	call LabDrillApply
	call LabSuppressPushdown
	call LabDrawScoreCarry
	ld   hl, GameState00_InGameMain
	ret




; ---------------------------------------------------------------------------
; Level picker and seed entry
;
; The original 0-9 grid is left completely alone - same tiles, same cursor, same
; movement. The Lab adds two fields in the blank strip to its right:
;
;        cols 15-18
;   row  6      .  L  .  .      level, 0-9 then A-M
;   row  9      S  E  E  D
;   row 10      A  C  E  1      seed, four hex digits
;
; Focus moves in a chain: grid -> level -> the four seed digits. Left and Right
; walk the chain, Up and Down change the value under the cursor. Right on grid
; cell 9 enters the level field - a press the original ignores, which is what
; makes the grid's own movement survive untouched. The focused field blinks.
;
; A seed of $0000 means "no seed", so SPS is off and pieces come from rDIV as
; they always did - which is genuinely random, so there is nothing to randomise.
; ---------------------------------------------------------------------------

DEF PICKER_CELL   EQU _SCRN0 + 6 * 32 + 16
DEF HEART_CELL    EQU _SCRN0 + 4 * 32 + 14
DEF TILE_HEART    EQU $27
DEF TILE_FRAME    EQU $2c       ; what the original draws in the heart cell
DEF TILE_BLANK    EQU $2f
DEF GRID_LAST     EQU 9

DEF FOCUS_GRID    EQU 0
DEF FOCUS_LEVEL   EQU 1
