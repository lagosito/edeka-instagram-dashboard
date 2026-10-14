#!/usr/bin/env python3
"""Historie mit dem Startstand befuellen.

Legt data/history/<DATUM>.json aus dem vorhandenen Beitrags-Datensatz plus den
Follower-Werten des Census an (Einmaliger Startschuss, danach laufen die
taeglichen Laeufe ueber scripts/scrape.py).
"""
import csv, json, os, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
HIST = os.path.join(DATA, 'history')

datum = sys.argv[1] if len(sys.argv) > 1 else '2026-10-11'
excl = {r['handle'] for r in csv.DictReader(open(os.path.join(DATA, 'excluded_accounts.csv'))) if r.get('handle')}
accounts = {r['handle']: r for r in csv.DictReader(open(os.path.join(DATA, 'accounts.csv')))}
# Basis des Startstandes: Census-Werte aus data/accounts.csv (Stand 11.10.)
# NICHT den Live-Stand nehmen, sonst ist die Basis identisch mit dem ersten Lauf.
follow = {}

bekannt = set()
os.makedirs(HIST, exist_ok=True)
for f in os.listdir(HIST):
    if f.endswith('.json') and f[:-5] != datum:
        for row in json.load(open(os.path.join(HIST, f))).get('neu', []):
            bekannt.add(row[0])

neu, seen = [], set()
for rec in json.load(open(os.path.join(DATA, 'posts_raw.json'))):
    h = rec['handle']
    if h in excl or h not in accounts:
        continue
    for p in rec.get('posts') or []:
        u = p.get('url')
        if not u or u in seen or u in bekannt:
            continue
        seen.add(u)
        lk = p.get('likes')
        valid = isinstance(lk, int) and lk >= 2
        neu.append([u, h, (lk if valid else None), p.get('comments'),
                    (p.get('taken_at') or '')[:10], ''])

follower = {h: int(follow[h]) if follow.get(h) else int(accounts[h]['followers'] or 0)
            for h in accounts if h not in excl}
snap = {'datum': datum, 'follower': follower, 'neu': neu}
json.dump(snap, open(os.path.join(HIST, datum + '.json'), 'w'), ensure_ascii=False,
          separators=(',', ':'))
print(f"Snapshot {datum}: {len(neu)} Beitraege, {len(follower)} Follower-Werte")
