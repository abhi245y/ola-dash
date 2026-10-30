#!/usr/bin/env bash
# Build the product APK on the build host (arlp-pc): SDK + themes/ bundled via EXTRA_THEMES.
# SDK_DIR=<checkout> builds an unpushed SDK instead of the sdk/ submodule pin.
set -euo pipefail
cd "$(dirname "$0")/.."
H=arlp-pc
D=Documents/ola-dash-build
ssh "$H" "mkdir -p $D"
# -rlp, not -a: preserved mtimes make cargo skip rebuilds of changed files.
rsync -rlp --checksum --delete --exclude .git --exclude tmp --exclude host/out --exclude host/build \
    --exclude host/target --exclude sim/target --exclude sim/out \
    "${SDK_DIR:-sdk}/" "$H:$D/"
rsync -rlp --checksum --delete themes/ "$H:$D/product-themes/"
ssh "$H" "cd ~/$D/host && EXTRA_THEMES=\$HOME/$D/product-themes ./build.sh"
mkdir -p out
scp "$H:$D/host/out/ola-dash-debug.apk" out/
