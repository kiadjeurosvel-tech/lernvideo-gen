#!/bin/bash
# Ver-/Entschlüsselung. Klartext liegt NUR zur Laufzeit auf dem Runner, nie im Repo.
E="openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:LV_PASSWORD"
D="openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:LV_PASSWORD"
case "$1" in
  open)   # Kurse + Arbeitsstand entschlüsseln
    mkdir -p kurse
    for p in enc/kurs_*.enc.part00; do b=${p%.part00}; cat "$b".part* | $D | tar xf - -C kurse; done
    [ -f enc/state.enc ] && $D < enc/state.enc | tar xf - ;;
  state)  # Arbeitsstand (Skripte) verschlüsselt sichern
    tar cf - skripte | $E > enc/state.enc ;;
  pack)   # Ergebnisse eines Fachs verschlüsseln -> rel/<Fach>.tar.enc
    mkdir -p rel; tar cf - -C out "$2" | $E > "rel/$2.tar.enc" ;;
esac
