#!/usr/bin/env python3
"""Meta Ads Library woechentlich abfragen (Deutschland, aktive Anzeigen).

Aufruf:  python3 scripts/scrape_ads.py
Ausgabe: data/ads/<marke>.json                       (aktueller Stand)
         data/ads_history/<YYYY-MM-DD>/<marke>.json  (Archiv pro Lauf)
Zusatz:  data/ads_meta.json mit Abfragedatum fuer die Anzeige im Dashboard.
"""
import json, os, subprocess, sys, time, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
QUERIES = [('edeka', 'EDEKA'), ('rewe', 'REWE'), ('lidl', 'Lidl'), ('aldi', 'ALDI'),
           ('netto', 'Netto'), ('kaufland', 'Kaufland'), ('penny', 'PENNY')]
MAXTRIES = 3


def search(q):
    payload = json.dumps({'query': q, 'active_status': 'active', 'country': 'DE', 'limit': 20})
    for i in range(MAXTRIES):
        try:
            p = subprocess.run(['treg', 'call', 'crawl4ai.meta-ads.library.search',
                                '--method', 'POST', '--data', payload],
                               capture_output=True, text=True, timeout=150)
            j = json.loads(p.stdout, strict=False)
            if j.get('error'):
                raise RuntimeError(str(j.get('error'))[:120])
            rows = j.get('rows') or []
            if rows:
                return rows
            raise RuntimeError('keine Treffer')
        except Exception as e:
            if i == MAXTRIES - 1:
                print(f'  {q}: FEHLER {str(e)[:100]}', flush=True)
                return None
            time.sleep(2 * (i + 1))


def main():
    heute = dt.datetime.now(dt.timezone(dt.timedelta(hours=2))).strftime('%Y-%m-%d')
    arch = os.path.join(DATA, 'ads_history', heute)
    os.makedirs(arch, exist_ok=True)
    fehler = 0
    for key, q in QUERIES:
        rows = search(q)
        if rows is None:
            fehler += 1
            continue
        out = {'abfrage': heute, 'query': q, 'rows': rows}
        json.dump(out, open(os.path.join(DATA, 'ads', key + '.json'), 'w'),
                  ensure_ascii=False, indent=1)
        json.dump(out, open(os.path.join(arch, key + '.json'), 'w'),
                  ensure_ascii=False, indent=1)
        print(f'{key}: {len(rows)} Treffer', flush=True)
        time.sleep(1)
    meta_path = os.path.join(DATA, 'ads_meta.json')
    if fehler < len(QUERIES):
        json.dump({'abfrage': heute}, open(meta_path, 'w'))
    if fehler >= len(QUERIES) * 0.5:
        print(f'FEHLER: {feehler}/{len(QUERIES)} Abfragen fehlgeschlagen')
        sys.exit(1)


if __name__ == '__main__':
    main()
