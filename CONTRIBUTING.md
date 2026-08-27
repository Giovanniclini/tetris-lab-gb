# Contributing

## Workflow

`main` is protected. Work happens on a branch and lands through a pull request
once CI is green. Without write access, fork first and open the PR from your
fork — the flow is otherwise the same.

```
git checkout -b short-description
# ... work, commit ...
git push -u origin short-description
gh pr create        # or open the PR in the browser
```

**One concept, one commit.** A branch that does one thing lands as one commit —
fixing your own work in progress is not a second concept. Squash before pushing.
Separate commits are for genuinely unrelated changes that share a branch, and
those are usually better as separate PRs. See `CLAUDE.md` §7a.

CI must pass before merging. What it checks:

| Check | Why it matters |
| --- | --- |
| `build.py --original` reproduces SHA-1 `74591cc9…` | **The project's ground truth.** If the stock ROM no longer rebuilds byte for byte, the change is wrong regardless of how it looks. |
| Banks 0-1 differ only at declared hooks | Catches accidental drift into original gameplay code |
| Byte-level tests | Gravity table, DAS constants, cartridge header |
| Behavioural tests | Drives the ROM in an emulator: level picker, instant restart, timings |
| No ROM data tracked | We ship patches, never ROM data |

macOS is checked weekly rather than per push: it queues badly and has never
caught anything Linux did not.

## Branch protection (applied)

Recorded here in case it ever needs re-applying. Under **Settings → Branches**,
`main` has:

- a pull request required before merging
- **`build and test`** required to pass (the job name in
  `.github/workflows/ci.yml`; it only becomes selectable after the workflow has
  run once)
- the branch required to be up to date with `main` before merging
- force pushes and deletions blocked
- **admin enforcement on** — the maintainer is bound by all of the above

Required approving reviews are **0**, because GitHub never lets you approve your
own pull request and the project is one person. That is what lets a solo
maintainer merge; admin enforcement is what stops anything landing red.

Nobody without write access can merge in any case: outside contributions arrive
as pull requests from forks, which only a collaborator can merge.

The same thing with the GitHub CLI, once `gh auth login` has been done:

```
gh api -X PUT repos/Giovanniclini/tetris-lab-gb/branches/main/protection \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=build and test' \
  -F 'enforce_admins=true' \
  -F 'required_pull_request_reviews[required_approving_review_count]=0' \
  -F 'restrictions=null'
```

## Running it locally

```
python3 build.py --original     # must print the byte-exact match
python3 build.py                # the Lab ROM
python3 tests/test_original.py
python3 tests/test_expansion.py
```

The behavioural tests need PyBoy, a test-only dependency:

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python tests/test_behaviour.py
.venv/bin/python tests/test_menu.py
.venv/bin/python tests/test_restart.py
.venv/bin/python tests/test_sps.py
.venv/bin/python tests/test_labmenu.py
.venv/bin/python tests/test_link.py
.venv/bin/python tests/test_hiscore.py
.venv/bin/python tests/test_pieces.py
.venv/bin/python tests/test_lfsr_vectors.py
.venv/bin/python tests/test_trep.py
```

### Editing the graphics

`python3 build.py` writes `build/tetrislab.trep.json` beside the ROM, the `.sym`
and the `.map`. Those four files are what [TREP](https://tolstoj-82.github.io/apps/trep/)
— Tolstoj's ROM editor — opens to show the tilesets and background maps as
editable pictures. Nothing in the build runs TREP; it reads what the build
publishes.

What TREP is for here: **designing**. A Lab screen's static background is a
20x18 layout in `src/lab/data/` and its tiles are a PNG in `src/lab/gfx/`, so a
design arrives back as a `.bin` and a `.png`; the labels, cursors and values on
top of them are drawn at runtime. Original layouts
in `src/original/data/` are shared with the `LAB=0` build and stay unedited —
changing one would break `--original`. See `docs/decisions/0012`.

`tetrislab.trep-source.json` is the catalogue. Its dimensions are load-bearing:
layouts carry no `.end` label, so a wrong figure shows a plausible wrong screen
with no error. `tests/test_trep.py` checks every one against the data on disk.

### Patch channels

Two pre-releases, each republished by CI once the test job passes. Their
download URLs never change, so a bookmark — or a phone — always fetches the
current build of that channel:

| channel | is | published on |
| --- | --- | --- |
| [`nightly`](https://github.com/Giovanniclini/tetris-lab-gb/releases/download/nightly/tetrislab.bps) | whatever `main` is now | every push to `main` |
| [`preview`](https://github.com/Giovanniclini/tetris-lab-gb/releases/download/preview/tetrislab.bps) | whatever is up for review | every pull request |

`preview` is the one that matters day to day: a build you can only try *after*
merging is a build you cannot use to decide whether to merge. Its release notes
name the pull request it came from.

Both exist so a build can be tried on a phone without being at the machine that
built it — apply the patch to your own ROM with a browser BPS patcher, then load
the result into an emulator. No ROM data is published: the patch is 2 KB and
your ROM stays on your device.

Each channel also carries `tetrislab.sym`, `tetrislab.map` and
`tetrislab.trep.json` — everything [TREP](https://tolstoj-82.github.io/apps/trep/)
needs beside a patched ROM to open the build and edit its screens. They are
symbol names and addresses, not ROM data.

`tools/nightly.sh [channel]` does either by hand, for a branch with no pull
request open yet. Both are pre-releases, so tagged releases keep the "Latest"
badge, and **neither ever carries a `.gb`** — see `CLAUDE.md` §10.

Fork pull requests are skipped: their token cannot write releases, and a fork
should not be able to publish to this repository anyway.

The README's screenshots come from the ROM, not from a folder of stale
captures. Regenerate them after a UI change:

```
.venv/bin/python tools/screenshots.py
```

The whole suite takes about 15 seconds.

## Before you write code

Read [`CLAUDE.md`](CLAUDE.md), then [`docs/decisions/`](docs/decisions/). The
ADRs record constraints found the hard way - bank switching, why hooks redirect
rather than insert, and the ordering traps in the level select and instant
restart. They will save you more time than they take to read.

**If a change adds a hook into the original banks**, declare it in
`src/hooks/hooks.inc`, mirror it in `tests/test_expansion.py`, and say why in
the PR. Those get extra review.
