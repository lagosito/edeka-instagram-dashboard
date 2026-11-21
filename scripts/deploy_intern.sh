#!/usr/bin/env bash
# Täglicher interner Deploy für das Vercel-Projekt "edeka-intern".
# Ablauf: nach dem GitHub-Run (update-dashboard, ca. 05:15 UTC):
#   pull -> interner Build -> Deploy -> Schutz-Check.
# LECK-SCHUTZ: Der interne Build läuft IMMER in einem separaten Git-Worktree
# AUSSERHALB des Repos. Die Repo-Dateien index.html/data/dashboard.json werden
# vorher zurückgesetzt (git checkout --), damit im Repo nie ein interner Stand
# committet werden kann.
set -euo pipefail

REPO="/Users/pablo/edeka-ig/site"
WT="/Users/pablo/edeka-intern-build"          # ausserhalb des Repos
PROD_ALIAS="edeka-intern.vercel.app"
REPO_SLUG="lagosito/edeka-instagram-dashboard"

fail() { echo "FEHLER: $1"; exit 1; }

# Vercel-Token (falls vorhanden) – niemals ausgeben
if [ -f "$HOME/.hermes/CREDENTIALS_MASTER.env" ]; then
  _T=$(grep '^VERCEL_DEPLOY_TOKEN=' "$HOME/.hermes/CREDENTIALS_MASTER.env" | head -1 | cut -d= -f2- | tr -d '"'\''\r\n' || true)
  if [ -n "${_T:-}" ]; then export VERCEL_DEPLOY_TOKEN="$_T"; fi
fi

cd "$REPO"

# 0) Kurz warten, bis der GitHub-Run (update-dashboard) fertig ist (max. 6 Min)
for _i in 1 2 3 4 5 6; do
  ST=$(gh run list --repo "$REPO_SLUG" --limit 1 --json status --jq '.[0].status' 2>/dev/null || echo completed)
  case "$ST" in in_progress|queued) sleep 60 ;; *) break ;; esac
done

# 1) Repo auf den öffentlichen Stand zurücksetzen + aktualisieren
git checkout -- index.html data/dashboard.json || fail "git checkout"
git pull --ff-only origin main || fail "git pull"

# 2) Frischer Git-Worktree AUSSERHALB des Repos (detached HEAD)
git worktree remove --force "$WT" 2>/dev/null || true
git worktree add --detach "$WT" HEAD || fail "git worktree add"

# 3) Interne Daten + Vercel-Link in den Worktree
if [ ! -d "$REPO/data/intern" ]; then fail "data/intern fehlt im Repo-Ordner"; fi
cp -R "$REPO/data/intern" "$WT/data/intern"
if [ -d "$REPO/.vercel" ]; then cp -R "$REPO/.vercel" "$WT/.vercel"; fi

# 4) Interner Build NUR im Worktree (Repo bleibt öffentlich)
cd "$WT"
python3 scripts/build.py >/dev/null || fail "build.py"
if [ ! -s index.html ]; then fail "index.html leer"; fi
grep -q "Jahresstart 2027" data/dashboard.json || fail "interner Content fehlt (Jahresstart)"

# 5) Deploy von dort aus nach Vercel
DEPLOY_OUT=$(vercel deploy --prod --yes 2>&1) || { printf '%s\n' "$DEPLOY_OUT" | tail -5; fail "vercel deploy"; }
URL=$(printf '%s\n' "$DEPLOY_OUT" | grep -m1 '^Production:' | grep -oE 'https://[^ ]+' | head -1 | sed 's|https://||')
if [ -z "$URL" ]; then printf '%s\n' "$DEPLOY_OUT" | tail -8; fail "keine Deployment-URL im Deploy-Output"; fi

# 6) Schutz-Check: anonym überall 401, mit Auth voller interner Content
sleep 12
C1=$(curl -s -o /dev/null -w '%{http_code}' "https://$URL/")
C2=$(curl -s -o /dev/null -w '%{http_code}' "https://$PROD_ALIAS/")
C3=$(curl -s -o /dev/null -w '%{http_code}' "https://$PROD_ALIAS/data/dashboard.json")
[ "$C1" = "401" ] || fail "Deployment-URL gibt $C1 statt 401"
[ "$C2" = "401" ] || fail "Alias $PROD_ALIAS gibt $C2 statt 401"
[ "$C3" = "401" ] || fail "Alias dashboard.json gibt $C3 statt 401"
# Auth-Check: Deployment-URL (kritisch) + Alias (informativ)
_ok=0
for _t in 1 2 3 4 5 6; do
  if vercel curl "/data/dashboard.json" --deployment "$URL" 2>/dev/null | grep -q "Jahresstart 2027"; then
    _ok=1; break
  fi
  sleep 10
done
[ "$_ok" = "1" ] || fail "interner Content nicht erreichbar (Deployment-Check)"
# Alias-Check (informativ, nicht fatal – der Alias stabilisiert sich in Minuten)
if vercel curl "/data/dashboard.json" --deployment "$PROD_ALIAS" 2>/dev/null | grep -q "Jahresstart 2027"; then
  echo "Alias OK: interner Content erreichbar"
else
  echo "WARNUNG: Alias hat noch nicht den internen Content (stabilisiert sich in Minuten)"
fi

# 7) Repo prüfen + Worktree entfernen (Repo nie mit internem Stand)
cd "$REPO"
git worktree remove --force "$WT" 2>/dev/null || true
if git status --porcelain index.html data/dashboard.json | grep -q .; then
  fail "Repo-Dateien sind NICHT sauber (interner Stand im Repo!)"
fi

echo "OK intern: $URL (401 anonym, Content mit Auth geprüft)"
