#!/bin/bash
# Nach jedem Fach: Arbeitsstand verschlüsselt committen, Ergebnisse verschlüsselt als Release.
F="$1"
git config user.name "lernvideo-bot"; git config user.email "actions@github.com"
bash crypt.sh state
git add enc/state.enc
git diff --cached --quiet || { git commit -qm "Arbeitsstand [skip ci]"; git pull -q --rebase; git push -q; }
[ -d "out/$F" ] && [ -n "$(ls -A "out/$F")" ] || exit 0
bash crypt.sh pack "$F"
TAG="lv-$(echo "$F" | tr '[:upper:]' '[:lower:]')-$(date +%Y%m%d-%H%M)"
gh release create "$TAG" "rel/$F.tar.enc" --title "$TAG" --notes "verschlüsselt" && rm -rf "out/$F" "rel/$F.tar.enc"
