#!/usr/bin/env bash
# Check committed previews against fresh renders, or regenerate them with --write.
# Usage: tools/check-previews.sh [--write] [theme-dir ...]
# Defaults to every themes/*/ with a theme.json.
# SIM=/path/to/sim uses an existing binary; otherwise build the release sim first.
# An SDK pin bump re-renders every preview (the host overlay is in the render),
# so bump PRs run tools/check-previews.sh --write.
set -euo pipefail
# A relative SIM is relative to the caller's directory.
case "${SIM:-}" in ""|/*) ;; *) SIM="$PWD/$SIM" ;; esac
cd "$(dirname "$0")/.."

write=false
if [ "${1:-}" = --write ]; then
    write=true
    shift
fi

if [ -z "${SIM:-}" ]; then
    cargo build --release --manifest-path "$PWD/sdk/sim/Cargo.toml" >&2
    SIM="$PWD/sdk/sim/target/release/sim"
fi

if [ "$#" -gt 0 ]; then
    themes=("$@")
else
    themes=(themes/*/)
fi

# ponytail: Byte comparison is deliberate: the software renderer with bundled fonts
# and the pure-Rust PNG encoder are deterministic. If renders ever differ between
# machines, use ImageMagick compare -metric AE -fuzz 1% with a small pixel-count threshold.
status=0
checked=0
for dir in "${themes[@]}"; do
    dir="${dir%/}"
    case "$dir" in -*) echo "error: unknown option $dir" >&2; exit 2 ;; esac
    if [ ! -f "$dir/theme.json" ]; then
        echo "skip: $dir (no theme.json)"
        continue
    fi
    checked=$((checked + 1))
    if ! "$SIM" "$dir" --contract "$PWD/sdk/contract" --write-preview; then
        echo "error: could not render $dir/preview.png" >&2
        status=1
        continue
    fi
    preview="$dir/preview.png"
    if [ "$write" = true ]; then
        continue
    fi
    if ! git diff --quiet -- "$preview"; then
        echo "error: $preview is stale" >&2
        status=1
    elif [ -n "$(git ls-files --others --exclude-standard -- "$preview")" ]; then
        echo "error: $preview is missing" >&2
        status=1
    else
        echo "ok: $preview"
    fi
done

if [ "$checked" -eq 0 ]; then
    echo "error: no themes with a theme.json found" >&2
    status=1
fi
if [ "$status" -ne 0 ] && [ "$write" = false ]; then
    echo 'regenerate with: tools/check-previews.sh --write (CI uploads the rendered previews as the "previews" artifact)' >&2
fi
exit "$status"
