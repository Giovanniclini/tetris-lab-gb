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
```

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
