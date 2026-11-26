#!/usr/bin/env python3
"""Plausibilitaetspruefung vor dem Commit.

Vergleicht den frisch erzeugten Stand mit dem zuletzt committeden:
  python3 scripts/validate.py
Bricht mit Exit 1 ab, wenn sich Konten- oder Beitragszahl um mehr als
20 % geaendert haben. Dann wird nichts committet.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEU = os.path.join(ROOT, 'data', 'dashboard.json')
MAX = 0.20


# --- Pausche 04 (Trends & Stimmen): Struktur, wenn die Dateien existieren ---
def check_neu(fn, zfeld, pflicht):
    pfad = os.path.join(ROOT, 'data', fn)
    if not os.path.exists(pfad):
        print(fn + ': nicht vorhanden (faellt sich montags automatisch)')
        return
    try:
        d = json.load(open(pfad, encoding='utf-8'))
    except Exception as e:
        print('ABBRUCH: %s ist kein gueltiges JSON: %s' % (fn, e))
        sys.exit(1)
    if not isinstance(d, dict):
        print('ABBRUCH: %s muss ein Objekt sein' % fn)
        sys.exit(1)
    n = d.get(zfeld)
    if not isinstance(n, (int, float)) or n < 0:
        print('ABBRUCH: %s: %s fehlt oder < 0' % (fn, zfeld))
        sys.exit(1)
    for k in pflicht:
        if k not in d:
            print('ABBRUCH: %s: Feld %s fehlt' % (fn, k))
            sys.exit(1)
    print('%s: ok (%s=%s)' % (fn, zfeld, n))


check_neu('trends.json', 'n_relevant', ['stand', 'kosten_usd', 'top', 'formate'])
check_neu('comments.json', 'n_kommentare',
          ['stand', 'kosten_usd', 'ton', 'themen', 'posts', 'fazit', 'aktionen'])
check_neu('retailers.json', 'n_reels', ['stand', 'kosten_usd', 'konten', 'formate', 'top'])


def old_dash():
    p = subprocess.run(['git', 'show', 'HEAD:data/dashboard.json'],
                       cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


if not os.path.exists(NEU):
    print('FEHLER: data/dashboard.json fehlt')
    sys.exit(1)

neu = json.load(open(NEU))
alt = old_dash()
if not alt:
    print('Hinweis: erster Lauf, kein Referenzstand vorhanden')
    sys.exit(0)

nk = [neu.get('kpi', {}), alt.get('kpi', {})]
checks = [('profile', 'Kontenzahl'), ('beitraege', 'Beitragszahl')]
problems = []
for key, label in checks:
    a, b = nk[0].get(key), nk[1].get(key)
    if not isinstance(a, int) or not isinstance(b, int) or b == 0:
        continue
    d = abs(a - b) / b
    print(f'{label}: {b} -> {a} ({d * 100:.1f} %)')
    if d > MAX:
        problems.append(f'{label} {b} -> {a} ({d * 100:.1f} %)')

if problems:
    print('ABBRUCH: ' + '; '.join(problems))
    sys.exit(1)
print('Plausibilitaetscheck ok')
sys.exit(0)
