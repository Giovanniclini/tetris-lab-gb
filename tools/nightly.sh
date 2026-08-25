#!/bin/sh
# Publish the current build's patch to a pre-release channel.
#
#   tools/nightly.sh [channel]      default: nightly
#
# Two channels, each a pre-release whose download URL never changes, so a
# bookmark - or a phone - always fetches the current build of that channel:
#
#   nightly   whatever main is now.       CI publishes it on every push to main.
#   preview   whatever is up for review.  CI publishes it on every pull request.
#
#   https://github.com/Giovanniclini/tetris-lab-gb/releases/download/<channel>/tetrislab.bps
#
# Each channel also carries the .sym, .map and .trep.json, which is everything
# TREP needs beside a patched ROM. They hold symbol names and addresses, not ROM
# data.
#
# preview exists because a build you can only try after merging is a build you
# cannot use to decide whether to merge.
#
# Runs by hand too, for a branch with no pull request open yet.
#
# Never attach a .gb. Releases carry the patch only - the patched ROM contains
# the original, and publishing it anywhere is distributing it. See CLAUDE.md 10.
set -e
cd "$(dirname "$0")/.."

channel="${1:-nightly}"
python3 build.py --patch >/dev/null

# --patch builds the Lab ROM before the stock one it diffs against, so the
# symbol, map and TREP files are all present by now. Never add the .gb.
artifacts="build/tetrislab.bps build/tetrislab.sym build/tetrislab.map build/tetrislab.trep.json"
sha=$(git rev-parse --short HEAD)
subject=$(git log -1 --pretty=%s)
built=$(date -u '+%Y-%m-%d %H:%M UTC')

if [ "$channel" = "nightly" ]; then
    title="nightly — latest main"
    what="Whatever \`main\` is now, at \`$sha\`."
else
    title="preview — latest build under review"
    what="A build that has **not** been merged: ${PREVIEW_LABEL:-branch $(git rev-parse --abbrev-ref HEAD)}, at \`$sha\`."
fi

notes=$(cat <<NOTES
**Unstable, and not a release.** $what It passed the test suite; that is all it
promises. Tagged releases are on the [releases page](../../releases).

Built $built from *$subject*.

### Using it on a phone

1. Keep your own **Tetris (World) (Rev A)** ROM on the device — SHA-1 \`74591cc9501af93873f9a5d3eb12da12c0723bbc\`.
2. Open \`tetrislab.bps\` below and apply it with a browser BPS patcher.
3. Load the result into a Game Boy emulator.

Your ROM never leaves your device, and no ROM data is published here.

### Designing screens

\`tetrislab.sym\`, \`tetrislab.map\` and \`tetrislab.trep.json\` are what
[TREP](https://tolstoj-82.github.io/apps/trep/) needs to open this build and show its
tilesets and background maps as editable pictures. Patch your own ROM as above, then point
TREP at it with these three alongside.
NOTES
)

if gh release view "$channel" >/dev/null 2>&1; then
    git tag -f "$channel" >/dev/null
    git push -f origin "$channel" >/dev/null
    gh release edit "$channel" --title "$title" --notes "$notes" >/dev/null
    gh release upload "$channel" $artifacts --clobber >/dev/null
else
    gh release create "$channel" $artifacts \
        --title "$title" --notes "$notes" --prerelease
fi

echo "published $sha to $channel -> $(gh release view "$channel" --json url -q .url)"
