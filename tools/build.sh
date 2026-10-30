#!/usr/bin/env bash
# Build the product APK on the build host (arlp-pc): SDK + themes/ bundled via EXTRA_THEMES.
# SDK_DIR=<checkout> builds an unpushed SDK instead of the sdk/ submodule pin.
set -euo pipefail
cd "$(dirname "$0")/.."
H=${BUILD_HOST:-arlp-pc}
D=${BUILD_DIR:-Documents/ola-dash-build}
SDK="${SDK_DIR:-sdk}"
[ -f "$SDK/host/build.sh" ] || { echo "no SDK in $SDK: run git submodule update --init" >&2; exit 1; }
ssh "$H" "mkdir -p $D"
# -rlp, not -a: preserved mtimes make cargo skip rebuilds of changed files.
rsync -rlp --checksum --delete --exclude .git --exclude tmp --exclude host/out --exclude host/build \
    --exclude host/target --exclude sim/target --exclude sim/out --exclude product-themes \
    "$SDK/" "$H:$D/"
rsync -rlp --checksum --delete themes/ "$H:$D/product-themes/"
ssh "$H" "cd ~/$D/host && EXTRA_THEMES=\$HOME/$D/product-themes ./build.sh"
mkdir -p out
scp "$H:$D/host/out/ola-dash-debug.apk" out/
unzip -l out/ola-dash-debug.apk | grep -q assets/themes/ || { echo "no themes bundled (SDK without EXTRA_THEMES?)" >&2; exit 1; }
