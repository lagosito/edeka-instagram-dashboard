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
