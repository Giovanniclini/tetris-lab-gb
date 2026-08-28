; --------------------------------------------------------------------------
; Instant restart
;
; A+B+Select+Start restarts the drill instead of rebooting the console.
; Four hooks, because four different pieces of the original reach the buttons
; first - see docs/decisions/0005.
; --------------------------------------------------------------------------

; --------------------------------------------------------------------------
; Quit to the level select
;
; B while paused. Changing level used to mean topping out on purpose, which is
; the wrong shape for a trainer - the loop is "try it, move the level, try it
; again". A+B+Select+Start keeps its own job, so the pair reads as "again"
; against "somewhere else".
;
; B is the button because it already means back here: it is how you leave the
; level select for the menu (ADR 0007). And while paused it is genuinely free -
; the game reads only the reset combination, Start to unpause, and Select, which
; hides the next piece ($1BF4). There is no free button during play.
; --------------------------------------------------------------------------

LabQuitToLevelSelect::
	ldh  a, [hGamePaused]
	and  a
	ret  z                          ; only from the pause screen

; Link play is not ours to leave. Quitting one side strands the other mid-game
; exactly as restarting it would, which is why ADR 0005 reboots there instead.
	ldh  a, [hIs2Player]
	and  a
	ret  nz

	ldh  a, [hButtonsPressed]
	bit  PADB_B, a
	ret  z

; B is also one quarter of the restart combination, so a restart pressed while
; paused arrives here first and would leave for the level select - which then
; reboots, because the combination is still held and menus reboot (ADR 0005).
; Decline while all four are down and let the restart have it.
	call LabResetComboHeld
	ret  z

; Unpause on the way out, and tell the sound engine so. Pausing sets
; wGamePausedActivity to 1 to stop the music ($1C34) and unpausing sets 2 to
; resume it ($1C5E); the level select never starts the music itself, so leaving
; without the resume signal is a silent menu. Same trap the instant restart hit.
	xor  a
	ldh  [hGamePaused], a
	ld   a, $02
	ld   [wGamePausedActivity], a

; Abandon the score rather than filing a game you walked out of - the same call
; ADR 0005 makes for the half-typed name. Zeroed here, so the level select's own
; filing finds nothing whichever mode was being played.
	xor  a
	ld   [wScoreBCD], a
	ld   [wScoreBCD + 1], a
	ld   [wScoreBCD + 2], a
	ld   [wLabScoreMillions], a
	ldh  [hMustEnterHighScore], a

; Back to the level select this game came from. B-type has its own, and sending
; a B-type game to the A-type screen would hand it the wrong level and the wrong
; screen. TRANSITION and CRUNCH are A-type games, so they land where TETRIS
; does - and wLabMode still holds the drill, so it is still selected when you
; start again.
	ldh  a, [hGameType]
	cp   GAME_TYPE_B_TYPE
	ld   a, GS_B_TYPE_SELECTION_INIT
	jr   z, .go
	ld   a, GS_A_TYPE_SELECTION_INIT
.go:
	ldh  [hGameState], a
	ret


; Z is set when the soft-reset combination is held.
LabResetComboHeld::
	ldh  a, [hButtonsHeld]
	and  PADF_START|PADF_SELECT|PADF_B|PADF_A
	cp   PADF_START|PADF_SELECT|PADF_B|PADF_A
	ret


LabInGameReset::
; Link play still reboots: restarting one side of a two-player game would
; desync the cable, and the original behaviour is the safe one there.
	ldh  a, [hIs2Player]
	and  a
	jp   nz, Reset

; A restart we started is still initialising: decline, and let it finish.
	ld   a, [wLabRestarting]
	and  a
	jr   z, .notRestarting

	ldh  a, [hGameState]
	cp   GS_IN_GAME_INIT
	jr   z, .consume

	xor  a                          ; init finished
	ld   [wLabRestarting], a

.notRestarting:
; Restart from anywhere inside a game or its aftermath. Topping out and going
; straight again is the case a trainer needs most, and the game-over sequence
; runs $00 -> $01 -> $0D -> $04 before it settles.
	ldh  a, [hGameState]
	and  a
	jr   z, .restart                ; GS_IN_GAME_MAIN
	cp   GS_GAME_OVER_INIT
	jr   z, .restart
	cp   GS_LEVEL_ENDED_MAIN
	jr   z, .restart
	cp   GS_GAME_OVER_SCREEN_CLEARING
	jr   z, .restart
	cp   GS_ENTERING_HIGH_SCORE
	jr   z, .restart

; Anywhere else, reboot exactly as the original does. Note this includes
; GS_IN_GAME_INIT reached from the level select, which is what happens when the
; combination is pressed on a menu - Start is part of it, so the menu starts a
; game on the way past. Only a restart we began is exempt, hence the flag.
	jp   Reset

.restart:
; Restart unpaused. Nothing in the original clears hGamePaused, because nothing
; in the original can start a game while paused - you cannot pause a menu. The
; instant restart can, and without this the new game comes up frozen with a
; piece sitting at the top until you press Start. Reported by baovofe67, and
; diagnosed by Giovanni: it only happens when the combination is fumbled and
; Start lands first.
;
; Clearing the flag is not enough on its own. Pausing tells the sound engine to
; stop the music by setting wGamePausedActivity to 1 ($1C34); unpausing tells it
; to resume by setting 2 ($1C5E), and the engine zeroes it once acted on. The
; in-game init never starts the music - it has been playing since the menu - so
; a restart that skips the unpause leaves it stopped for good. Send the engine
; its own resume signal rather than inventing one.
	ldh  a, [hGamePaused]
	and  a
	jr   z, .wasNotPaused

	xor  a
	ldh  [hGamePaused], a
	ld   a, $02
	ld   [wGamePausedActivity], a

.wasNotPaused:

	ld   a, GS_IN_GAME_INIT
	ldh  [hGameState], a
	ld   a, 1
	ld   [wLabRestarting], a

; Consume the combination. MainLoop's check runs later in this same frame, and
; during the restart's init frames it is the only one that runs at all.
; PollInput refills hButtonsHeld next frame.
.consume:
	xor  a
	ldh  [hButtonsHeld], a
	ret
