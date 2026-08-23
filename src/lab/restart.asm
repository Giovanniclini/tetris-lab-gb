; --------------------------------------------------------------------------
; Instant restart
;
; A+B+Select+Start restarts the drill instead of rebooting the console.
; Four hooks, because four different pieces of the original reach the buttons
; first - see docs/decisions/0005.
; --------------------------------------------------------------------------

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
