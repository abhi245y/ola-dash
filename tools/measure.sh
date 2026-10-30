#!/usr/bin/env bash
# Session-A timings per theme on the dev scooter (debug build, adb).
#   tools/measure.sh [--dry-run]
# Pushes every theme in $SDK_DIR/themes (default sdk/themes), cycles files/themes/active,
# restarts the app, collects OlaDash timings, Displayed time and PSS, appends a row per
# theme to docs/measurements.md and restores the original `active`. ADB_SERIAL optional.
set -euo pipefail
cd "$(dirname "$0")/.."
SDK_DIR=${SDK_DIR:-sdk}
PKG=dev.olatool.dash
OUT=docs/measurements.md
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
[ "$DRY" = 1 ] || [ $# -eq 0 ] || { echo "usage: $0 [--dry-run]" >&2; exit 2; }

ADB=(adb ${ADB_SERIAL:+-s "$ADB_SERIAL"})
# run: print the command in a dry run, else execute it
run() { if [ "$DRY" = 1 ]; then echo "+ ${ADB[*]} $*" >&2; else "${ADB[@]}" "$@"; fi; }
# in-app shell line
ras() { run shell run-as "$PKG" sh -c "'$1'"; }

themes=()
for d in "$SDK_DIR"/themes/*/; do [ -f "$d/theme.json" ] && themes+=("$(basename "$d")"); done
[ ${#themes[@]} -gt 0 ] || { echo "no themes under $SDK_DIR/themes" >&2; exit 1; }

orig=$([ "$DRY" = 1 ] && echo ORIGINAL || "${ADB[@]}" shell run-as "$PKG" cat files/themes/active 2>/dev/null | tr -d '\r\n' || true)
restore() { if [ -n "$orig" ]; then ras "echo $orig > files/themes/active"; else ras "rm -f files/themes/active"; fi; }
trap restore EXIT

for t in "${themes[@]}"; do
  run push "$SDK_DIR/themes/$t" "/data/local/tmp/t/$t" >/dev/null
  ras "mkdir -p files/themes && cp -r /data/local/tmp/t/$t files/themes/"
done

date=$(date +%F)
rows=
for t in "${themes[@]}"; do
  echo "== $t" >&2
  ras "echo $t > files/themes/active"
  run logcat -c
  run shell am force-stop "$PKG"
  run shell am start -n "$PKG/.MainActivity"
  if [ "$DRY" = 1 ]; then
    echo "+ wait <=30 s for 'timing first-frame' in: ${ADB[*]} logcat -d -s OlaDash" >&2
    echo "+ sleep 10" >&2
    run shell dumpsys meminfo "$PKG"
    rows+="| $date | $t | <probe> | <root> | <create> | <first-frame> | <displayed> | <pss KB> |"$'\n'
    continue
  fi
  for _ in $(seq 30); do
    "${ADB[@]}" logcat -d -s OlaDash | grep -q 'timing first-frame' && break
    sleep 1
  done
  log=$("${ADB[@]}" logcat -d -s OlaDash ActivityManager)
  ms() { grep -o "timing $1 [0-9]* ms" <<<"$log" | tail -1 | awk '{print $3}'; }
  disp=$(grep -o "Displayed $PKG/[^ ]*: +[^ ]*" <<<"$log" | tail -1 | sed 's/.*: +//')
  sleep 10
  pss=$("${ADB[@]}" shell dumpsys meminfo "$PKG" | grep 'TOTAL PSS' | awk '{print $3}')
  rows+="| $date | $t | $(ms probe) | $(ms root) | $(ms create) | $(ms first-frame) | $disp | $pss |"$'\n'
done

printf '%s' "$rows"
if [ "$DRY" = 0 ]; then
  { printf '\n### %s\n\n' "$(date '+%F %H:%M') measure.sh"
    echo '| Date | Theme | probe ms | root ms | create ms | first-frame ms | Displayed | PSS KB |'
    echo '|---|---|---|---|---|---|---|---|'
    printf '%s' "$rows"; } >> "$OUT"
fi
