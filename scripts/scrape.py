#!/usr/bin/env python3
"""Beitraege und Follower aller Census-Konten per treg holen.

Aufruf:  python3 scripts/scrape.py [--posts-only|--profiles-only]
Ausgabe: data/posts_raw.json   [{handle, posts:[...]}, ...]
         data/followers.json   {handle: follower}

Auth in CI:  treg login --token "$TREG_TOKEN"   (vorher)
Konkurrenz: max. 3 parallele Calls (treg-Saettigung), 3 Versuche mit Backoff.
Exit-Codes: 0 ok, 1 wenn weniger als 80 % der Calls erfolgreich waren.
"""
import csv, json, os, subprocess, sys, time, datetime as dt, concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
WORKERS = 3
MIN_RATE = 0.80

only_posts = '--profiles-only' in sys.argv
only_profiles = '--posts-only' in sys.argv

handles = [r['handle'] for r in csv.DictReader(open(os.path.join(DATA, 'accounts.csv')))]


def call(endpoint, payload, attempts=2):
    for i in range(attempts):
        try:
            p = subprocess.run(['treg', 'call', endpoint, '--method', 'POST',
                                '--data', json.dumps(payload)],
                               capture_output=True, text=True, timeout=150)
            j = json.loads(p.stdout, strict=False)
            if j.get('error'):
                raise RuntimeError(str(j.get('error'))[:120])
            return j
        except Exception as e:
            if i == attempts - 1:
                return {'_error': str(e)[:160]}
            time.sleep(1.5 * (2 ** i))
    return {'_error': 'unbekannt'}


def fetch_posts(h):
    for versuch in range(3):
        j = call('crawl4ai.instagram.user.posts', {'username': h}, attempts=2)
        if '_error' in j:
            if versuch == 2:
                return h, None, j['_error']
            time.sleep(2 * (versuch + 1))
            continue
        rows = j.get('rows') or []
        if not rows:
            if versuch == 2:
                return h, [], 'keine Beitraege (wirklich leer)'
            time.sleep(2 * (versuch + 1))
            continue
        return h, rows, None
    return h, None, 'unbekannt'
    rows = j.get('rows') or []
    if not rows:
        # leere Antwort ist meist transient -> wie Fehler behandeln und wiederholen
        raise RuntimeError('leere Antwort')
    return h, rows, None


def fetch_profile(h):
    j = call('crawl4ai.instagram.user.profile', {'username': h})
    if '_error' in j:
        return h, None, j['_error']
    rows = j.get('rows') or []
    if not rows:
        return h, None, 'kein Profil'
    f = rows[0].get('followers')
    if not isinstance(f, (int, float)):
        return h, None, 'kein Follower-Wert'
    return h, int(f), None


def update_dataset_date():
    """Scrape-Datum und Census-Zahl in data/dataset.json fortschreiben."""
    path = os.path.join(DATA, 'dataset.json')
    try:
        meta = json.load(open(path))
    except Exception:
        meta = {}
    try:
        from zoneinfo import ZoneInfo
        heute = dt.datetime.now(ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%d')
    except Exception:
        heute = dt.datetime.now(dt.timezone(dt.timedelta(hours=2))).strftime('%Y-%m-%d')
    meta['scrape_date'] = heute
    meta['accounts_scanned'] = len(handles)
    json.dump(meta, open(path, 'w'), ensure_ascii=False, indent=2)


def run(fn, workers=WORKERS):
    out, errs = {}, {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for h, val, err in ex.map(fn, handles):
            if val is None:
                errs[h] = err
            else:
                out[h] = val
    return out, errs


ok = True

if not only_profiles:
    posts, errs = run(fetch_posts)
    if len(posts) < len(handles) * MIN_RATE:
        print(f'FEHLER: nur {len(posts)}/{len(handles)} Profile mit Beitraegen abrufbar', flush=True)
        ok = False
    records = [{'handle': h, 'posts': posts.get(h, [])} for h in handles]
    # nur schreiben, wenn der Lauf tragfaehig ist (letzter guter Stand bleibt sonst stehen)
    if ok:
        json.dump(records, open(os.path.join(DATA, 'posts_raw.json'), 'w'),
                  ensure_ascii=False, indent=1)
    print(f'Beitraege: {len(posts)}/{len(handles)} ok, {len(errs)} Fehler', flush=True)
    update_dataset_date()
    for h, e in list(errs.items())[:5]:
        print(f'   {h}: {e}', flush=True)

if not only_posts:
    prof, errs = run(fetch_profile)
    if len(prof) < len(handles) * MIN_RATE:
        print(f'FEHLER: nur {len(prof)}/{len(handles)} Profile abrufbar', flush=True)
        ok = False
    if ok:
        json.dump(prof, open(os.path.join(DATA, 'followers.json'), 'w'),
                  ensure_ascii=False, indent=1)
    print(f'Follower: {len(prof)}/{len(handles)} ok, {len(errs)} Fehler', flush=True)

sys.exit(0 if ok else 1)
