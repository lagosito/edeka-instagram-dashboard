#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EDEKA Social-Media- & Marketing-Intelligence-Dashboard (deutsch, 5 Abschnitte)."""
import csv, json, statistics, datetime as dt, html, os, subprocess, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # Repo-Root
DATA = os.path.join(ROOT, 'data')
CSV = os.path.join(DATA, 'accounts.csv')
RAW = os.path.join(DATA, 'posts_raw.json')
SITE = ROOT
IMG = os.path.join(SITE, 'img')
os.makedirs(IMG, exist_ok=True)

try:
    from zoneinfo import ZoneInfo
    BERLIN = ZoneInfo('Europe/Berlin')
except Exception:                      # Fallback: Sommerzeit (gilt fuer den Datensatz)
    BERLIN = dt.timezone(dt.timedelta(hours=2))

def ni(x):
    try:
        return int(x)
    except Exception:
        return 0

def de(v, dec=0):
    if isinstance(v, float):
        s = f"{v:,.{dec}f}"
    else:
        s = f"{int(v):,}"
    return s.replace(',', '§').replace('.', ',').replace('§', '.')

def esc(s):
    return html.escape(str(s or ''))

# ---------------- Filterregeln (v3) ----------------
# 1.1 Konten ausschliessen: nicht in Deutschland / kein EDEKA-Markt
def _load_excluded():
    path = os.path.join(DATA, 'excluded_accounts.csv')
    out = {}
    if os.path.exists(path):
        for row in csv.DictReader(open(path)):
            if row.get('handle'):
                out[row['handle']] = row.get('grund', '')
    return out

EXCLUDED = _load_excluded()
EXCL_LOG = []          # (handle, grund) tatsaechlich aus dem Datensatz entfernt

# 1.1 Beitraege fremder Owner: owner weder das Profil selbst noch EDEKA-Verbund
_OWNER_EDEKA = re.compile(r'edeka|marktkauf|e[._-]?center|ecenter|nordfrische', re.I)

def owner_ok(handle, owner):
    o = (owner or '').strip()
    if not o or o.lower() == handle.lower():
        return True
    return bool(_OWNER_EDEKA.search(o))

# 1.2 Like-Wert verfuegbar: 0 und 1 gelten als nicht geliefert
def likes_ok(post):
    lk = post.get('likes')
    return isinstance(lk, int) and lk >= 2

N_FREMDE = 0            # Beitraege fremder Owner (entfernt)
N_NO_LIKES = 0          # Beitraege ohne Like-Wert (fuer Auswertungen ausgeblendet)

# ---------------- Daten ----------------
profiles = {r['handle']: r for r in csv.DictReader(open(CSV))}
# Laufender Scraping-Lauf liefert aktuelle Follower (data/followers.json)
LIVE_FOLLOWER = json.load(open(os.path.join(DATA, 'followers.json')))     if os.path.exists(os.path.join(DATA, 'followers.json')) else {}
for _h, _f in LIVE_FOLLOWER.items():
    if _h in profiles and isinstance(_f, (int, float)) and _f:
        profiles[_h]['followers'] = str(int(_f))
accounts, posts = [], []
seen_urls = set()
for rec in json.load(open(RAW)):
    h = rec['handle']
    p = profiles.get(h)
    if not p:
        continue
    if h in EXCLUDED:
        if rec.get('posts'):
            EXCL_LOG.append((h, EXCLUDED[h]))
        continue
    plist = rec.get('posts') or []
    if not plist:
        continue
    followers = ni(p['followers'])
    ers, likes, coms, r30 = [], [], [], 0
    n_valid = 0
    kept = 0
    for post in plist:
        url = post.get('url')
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        if not owner_ok(h, post.get('owner')):
            N_FREMDE += 1
            continue
        valid = likes_ok(post)
        if valid:
            n_valid += 1
        else:
            N_NO_LIKES += 1
        lk = post.get('likes') if valid else 0
        cm = post.get('comments') if isinstance(post.get('comments'), int) else 0
        if valid:
            likes.append(lk); coms.append(cm)
            if followers:
                ers.append((lk + cm) / followers * 100)
        ts = post.get('taken_at')
        if ts:
            try:
                d = dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
                if (dt.datetime(2026, 10, 11, tzinfo=dt.timezone.utc) - d).days <= 30:
                    r30 += 1
            except Exception:
                pass
        q = dict(post); q['handle'] = h; q['followers'] = followers
        q['name'] = p['nombre']; q['tipo'] = p['tipo']; q['likes_ok'] = valid
        posts.append(q); kept += 1
    accounts.append({
        'handle': h, 'nombre': p['nombre'] or h, 'followers': followers, 'tipo': p['tipo'],
        'n': kept, 'n_valid': n_valid,
        'avg_likes': statistics.mean(likes) if likes else 0,
        'med_likes': statistics.median(likes) if likes else 0,
        'er': statistics.mean(ers) if ers else 0,
        'er_med': statistics.median(ers) if ers else 0,
        'r30': r30, 'inter': sum(likes) + sum(coms),
        'med_inter': statistics.median([(x + y) for x, y in zip(likes, coms)]) if likes else 0,
        'er_pool': list(ers),
        'url': f"https://www.instagram.com/{h}/",
    })

# Datenstand: Scrape-Datum des Datensatzes (data/dataset.json)
META = json.load(open(os.path.join(DATA, 'dataset.json')))
_dates = []
for _p in posts:
    _ts = _p.get('taken_at')
    if _ts:
        try:
            _dates.append(dt.datetime.fromisoformat(_ts.replace('Z', '+00:00')))
        except Exception:
            pass
STAND = dt.datetime.strptime(META['scrape_date'], '%Y-%m-%d').strftime('%d.%m.%Y')
LAUF = dt.datetime.now(BERLIN).strftime('%d.%m.%Y %H:%M')
# Abfragedatum der Werbeanzeigen: eigene Lauf-Metadaten, sonst Datensatz-Angabe
_AM = os.path.join(DATA, 'ads_meta.json')
if os.path.exists(_AM):
    try:
        _ads_q = dt.datetime.strptime(json.load(open(_AM))['abfrage'], '%Y-%m-%d').strftime('%d.%m.%Y')
    except Exception:
        _ads_q = dt.datetime.strptime(META.get('ads_query_date', META['scrape_date']), '%Y-%m-%d').strftime('%d.%m.%Y')
else:
    _ads_q = dt.datetime.strptime(META.get('ads_query_date', META['scrape_date']), '%Y-%m-%d').strftime('%d.%m.%Y')
STAND_ADS = _ads_q
now = dt.datetime.strptime(META['scrape_date'], '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)
TZ_LABEL = 'MESZ' if now.astimezone(BERLIN).utcoffset() == dt.timedelta(hours=2) else 'MEZ'
N_GES = len([r for r in json.load(open(RAW))])            # Konten im Urdatensatz
N_AUSGESCHLOSSEN = len(EXCL_LOG)
N_FREMDE_POSTS = N_FREMDE
N_KONTEN = len(accounts)
N_FOLLOWER = sum(a['followers'] for a in accounts)
N_POSTS = sum(a['n'] for a in accounts)
META_TEXT = f"Stand {LAUF.split()[0]} · {de(N_KONTEN)} Profile"
N_AKTIV30 = len([a for a in accounts if a['r30'] > 0])
PCT_AKTIV = N_AKTIV30 / N_KONTEN * 100 if N_KONTEN else 0
OER = statistics.mean([a['er'] for a in accounts if a['followers'] >= 500]) if accounts else 0
OER_MED = statistics.median([a['er'] for a in accounts if a['followers'] >= 500]) if accounts else 0
O_INT_POST = statistics.mean([(a['inter'] / a['n']) for a in accounts if a['n']]) if accounts else 0

# Ranking: nur Konten mit Like-Werten (mind. 6 Beitraege mit Like-Wert)
MOV_MIN = 6
mov = sorted([a for a in accounts if a['followers'] >= 500 and a['n_valid'] >= MOV_MIN],
             key=lambda a: -a['er'])
mov_med = sorted([a for a in accounts if a['followers'] >= 500 and a['n_valid'] >= MOV_MIN],
                 key=lambda a: -a['er_med'])
aktiv = sorted(accounts, key=lambda a: (-a['r30'], -a['inter']))
best_posts = sorted([p for p in posts if p.get('likes_ok')], key=lambda p: -p['likes'])
worst_pool = [p for p in posts if p.get('likes_ok') and p['followers'] >= 500]
worst_posts = sorted(worst_pool, key=lambda p: (p.get('likes', 0) + (p.get('comments') or 0)))[:20]
n_null_likes = N_NO_LIKES
N_POSTS_GUELTIG = len([p for p in posts if p.get('likes_ok')])

# Phase 3: Überflieger (Lift = Interaktionen des Beitrags / Median-Interaktionen des eigenen Kontos)
_acc_idx = {a['handle']: a for a in accounts}
_flieger = []
for _p in posts:
    if not _p.get('likes_ok'):
        continue
    _a = _acc_idx.get(_p['handle'])
    if not _a or _a['n_valid'] < MOV_MIN or not _a['med_inter']:
        continue
    _inter = (_p.get('likes') or 0) + (_p.get('comments') or 0)
    _lift = _inter / _a['med_inter']
    if _lift >= 3:
        _q = dict(_p); _q['lift'] = _lift
        _flieger.append(_q)
ueberflieger = sorted(_flieger, key=lambda x: -x['lift'])[:20]
_FMT_MAP = {'reel': 'Reels', 'carousel': 'Karussell', 'photo': 'Foto', 'video': 'Video'}
FL_FMT = collections.Counter(_FMT_MAP.get(x.get('kind'), 'Video') for x in ueberflieger)
FL_TAGS = collections.Counter()
for x in ueberflieger:
    for t in re.findall(r'#(\w{3,30})', x.get('caption') or ''):
        FL_TAGS[t.lower()] += 1
FL_INSIGHT = ('Darin dominiert {0} ({1} von {2}), häufigste Themen: {3}.'
              .format(FL_FMT.most_common(1)[0][0] if FL_FMT else 'kein Format',
                      FL_FMT.most_common(1)[0][1] if FL_FMT else 0, len(ueberflieger),
                      ', '.join('#' + t for t, c in FL_TAGS.most_common(3)) or 'keine Hashtags')) if ueberflieger else 'Keine Beiträge mit dem Dreifachen des Normalwerts.'

# Vergleich 30 Tage
def in_days(p, a, b):
    ts = p.get('taken_at')
    if not ts:
        return False
    try:
        d = dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        return False
    diff = (now - d).days
    return a <= diff < b
cur = [p for p in posts if in_days(p, 0, 30)]
prev = [p for p in posts if in_days(p, 30, 60)]
def inter(lst):
    return sum((x.get('likes') or 0) + (x.get('comments') or 0) for x in lst)
CUR_N, CUR_I = len(cur), inter(cur)
PREV_N, PREV_I = len(prev), inter(prev)
D_POSTS = (CUR_N - PREV_N) / PREV_N * 100 if PREV_N else 0
D_INT = (CUR_I - PREV_I) / PREV_I * 100 if PREV_I else 0

# Wochenverlauf (12 Wochen)
# Abdeckung je Konto = Datum des 12. (aeltesten) Beitrags im Fenster.
# Eine Woche gilt nur als voll abgedeckt, wenn ALLE Konten zurueckreichen.
wk_int = [0] * 12
wk_cnt = [0] * 12
wk_lab = []
for i in range(12):
    end = now - dt.timedelta(days=7 * (11 - i))
    wk_lab.append(end.strftime('%d.%m'))
for p in posts:
    ts = p.get('taken_at')
    if not ts:
        continue
    try:
        d = dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        continue
    diff = (now - d).days
    if diff < 0:
        continue
    idx = 11 - (diff // 7)
    if 0 <= idx <= 11 and p.get('likes_ok'):
        wk_int[idx] += (p.get('likes') or 0) + (p.get('comments') or 0)
        wk_cnt[idx] += 1

# Abdeckung aller Konten (Datum des 12. aeltesten Beitrags je Konto)
_cover = []
for _a in accounts:
    _ds = sorted([dt.datetime.fromisoformat(q['taken_at'].replace('Z', '+00:00'))
                  for q in posts if q['handle'] == _a['handle'] and q.get('taken_at')],
                 reverse=True)
    if _ds:
        _cover.append(_ds[11] if len(_ds) >= 12 else _ds[-1])
COVER_START = max(_cover) if _cover else now
FULL_WEEKS = len([i for i in range(12)
                  if (now - dt.timedelta(days=7 * (11 - i) + 6)) >=
                  COVER_START.replace(hour=0, minute=0, second=0, microsecond=0)])
# Bei weniger als 4 voll abgedeckten Wochen: normalisiert je Beitrag (kein Volumen-Bias)
wk_ipost = [(wk_int[i] / wk_cnt[i]) if wk_cnt[i] else 0 for i in range(12)]
USE_NORM = FULL_WEEKS < 4

# Formate
fmt = collections.defaultdict(lambda: {'n': 0, 'likes': [], 'er': []})
for p in posts:
    if not p.get('likes_ok'):
        continue
    k = p.get('kind') or 'video'
    lk = p.get('likes') or 0
    cm = p.get('comments') or 0
    fmt[k]['n'] += 1
    fmt[k]['likes'].append(lk)
    if p['followers']:
        fmt[k]['er'].append((lk + cm) / p['followers'] * 100)
FMT_DE = {'reel': 'Reels', 'carousel': 'Karussell', 'photo': 'Foto', 'video': 'Video'}
def p90(vals):
    if not vals:
        return 0
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(0.9 * (len(v) - 1))))]

fmt_rows = sorted([{'key': k, 'label': FMT_DE.get(k, k), 'n': v['n'],
                    'mean_likes': statistics.mean(v['likes']) if v['likes'] else 0,
                    'er': statistics.mean(v['er']) if v['er'] else 0,
                    'er_med': statistics.median(v['er']) if v['er'] else 0}
                   for k, v in fmt.items()], key=lambda x: -x['er'])
fmt_p90 = {k: p90(v['er']) for k, v in fmt.items()}
# Aussagekraeftig erst ab 30 Beitraegen je Format (Fallback: alles)
_stark = [r for r in fmt_rows if r['n'] >= 30] or fmt_rows
FMT_MED_BEST = max(_stark, key=lambda r: r['er_med']) if _stark else {'label': '-', 'er_med': 0, 'n': 0}
_kandidaten = [k for k, v in fmt.items() if v['n'] >= 30] or list(fmt_p90)
FMT_P90_BEST = (max(_kandidaten, key=lambda k: fmt_p90[k]) if _kandidaten and fmt_p90 else None)
FMT_P90_LABEL = FMT_DE.get(FMT_P90_BEST, FMT_P90_BEST) if FMT_P90_BEST else '-'
FMT_P90_VAL = fmt_p90.get(FMT_P90_BEST, 0) if FMT_P90_BEST else 0

# Zeitfenster-Analyse
WD_DE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
WD_EN = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
wd = collections.defaultdict(lambda: {'n': 0, 'er': []})
hr = collections.defaultdict(lambda: {'n': 0, 'er': []})
for p in posts:
    if not p.get('likes_ok'):
        continue
    ts = p.get('taken_at')
    if not ts:
        continue
    try:
        d0 = dt.datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(BERLIN)
    except Exception:
        continue
    lk = p.get('likes') if isinstance(p.get('likes'), int) else 0
    cm = p.get('comments') if isinstance(p.get('comments'), int) else 0
    if not p['followers']:
        continue
    e = (lk + cm) / p['followers'] * 100
    k = WD_EN.index(d0.strftime('%a'))
    wd[k]['n'] += 1; wd[k]['er'].append(e)
    hr[d0.hour]['n'] += 1; hr[d0.hour]['er'].append(e)
WD_ROWS = [{'label': WD_DE[k], 'n': wd[k]['n'],
            'er': statistics.mean(wd[k]['er']) if wd[k]['er'] else 0,
            'med': statistics.median(wd[k]['er']) if wd[k]['er'] else 0} for k in range(7)]
HR_ROWS = [{'h': h, 'n': hr[h]['n'],
            'er': statistics.mean(hr[h]['er']) if hr[h]['er'] else 0,
            'med': statistics.median(hr[h]['er']) if hr[h]['er'] else 0}
           for h in sorted(hr) if hr[h]['n'] >= 40]
best_day = max(WD_ROWS, key=lambda r: r['med'])
WD_ORD = sorted([r for r in WD_ROWS if r['n'] >= 20], key=lambda r: -r['med'])
if len(WD_ORD) >= 4:
    TAGE_TEXT = ('{0} (Median {1} %), danach {2} und {3}; schwächster Tag ist {4} ({5} %)'
                 .format(WD_ORD[0]['label'], de(WD_ORD[0]['med'], 2), WD_ORD[1]['label'], WD_ORD[2]['label'],
                         WD_ORD[-1]['label'], de(WD_ORD[-1]['med'], 2)))
elif WD_ORD:
    TAGE_TEXT = '{0} (Median {1} %)'.format(WD_ORD[0]['label'], de(WD_ORD[0]['med'], 2))
else:
    TAGE_TEXT = best_day['label']
best_hours = sorted(HR_ROWS, key=lambda r: -r['med'])[:3]
_vol_18 = next((r['n'] for r in HR_ROWS if r['h'] == 18), 0)
ZEIT_TEXT = ('stärkste Median-Werte um {0}, während um 18:00 Uhr mit {1} Beiträgen am häufigsten gepostet wird und der Median dort sinkt'
             .format(', '.join(f"{r['h']}:00 ({de(r['med'], 2)} %)" for r in best_hours), de(_vol_18)))


# ---------------- Phase 4: Themen ----------------
THEMES_PATH = os.path.join(DATA, 'themes.json')
_thema_map = {}
if os.path.exists(THEMES_PATH):
    for _r in json.load(open(THEMES_PATH)):
        _thema_map[_r['id']] = _r['thema']
KATEGORIEN = ["Angebot/Preis", "Rezept/Food", "Gesund/Bio/Protein", "Humor/Team/Azubi", "Region/Lieferant",
              "Recruiting/Karriere", "Gewinnspiel", "Event/Aktion", "Sonstiges"]

for _p in posts:
    _p['thema'] = _thema_map.get(_p.get('url'), 'nicht zugeordnet')

_themen = collections.defaultdict(lambda: {'n': 0, 'er': [], 'inter': []})
for _p in posts:
    if not _p.get('likes_ok'):
        continue
    t = _p['thema']
    _themen[t]['n'] += 1
    if _p['followers']:
        _themen[t]['er'].append(((_p.get('likes') or 0) + (_p.get('comments') or 0)) / _p['followers'] * 100)

def p90_of(vals):
    if not vals:
        return 0
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(0.9 * (len(v) - 1))))]

THEMEN_ROWS = []
for t in KATEGORIEN + [k for k in _themen if k not in KATEGORIEN]:
    if t not in _themen or t == 'nicht zugeordnet':
        continue
    d = _themen[t]
    THEMEN_ROWS.append({'thema': t, 'n': d['n'],
                        'med': statistics.median(d['er']) if d['er'] else 0,
                        'mean': statistics.mean(d['er']) if d['er'] else 0,
                        'p90': p90_of(d['er'])})
THEMEN_ROWS.sort(key=lambda r: -r['med'])
N_KLASSIFIZIERT = len([p for p in posts if p.get('thema') != 'nicht zugeordnet'])

# Thema x Format: Median-ER, Zellen ab 10 Beitraegen
_MATRIX = collections.defaultdict(list)
for _p in posts:
    if not _p.get('likes_ok') or not _p['followers']:
        continue
    _MATRIX[(_p['thema'], _p.get('kind'))].append(
        ((_p.get('likes') or 0) + (_p.get('comments') or 0)) / _p['followers'] * 100)

def matrix_html():
    kinds = ['reel', 'carousel', 'photo', 'video']
    head = '<tr><th>Thema</th>' + ''.join(f'<th class="num">{FMT_DE.get(k, k)}</th>' for k in kinds) + '</tr>'
    rows = []
    for r in THEMEN_ROWS:
        cells = []
        for k in kinds:
            vals = _MATRIX.get((r['thema'], k), [])
            if len(vals) >= 10:
                cells.append(f'<td class="num">{de(statistics.median(vals), 2)}</td>')
            else:
                cells.append('<td class="num muted">–</td>')
        rows.append(f'<tr><td>{esc(r["thema"])}</td>' + ''.join(cells) + '</tr>')
    return '<div class="tw"><table><thead>' + head + '</thead><tbody>' + ''.join(rows) + '</tbody></table></div>'

def themen_bars():
    out = []
    mx = max([r['med'] for r in THEMEN_ROWS]) or 1
    nrm = min(100.0, (POST_MED / mx) * 100)
    for r in THEMEN_ROWS:
        w = max(4, r['med'] / mx * 100)
        klein = r['n'] < 20
        klasse = 'klein' if klein else _rel(r['med'])[0]
        farbe = '#E7E4DC' if klein else ('#2A60FF' if klasse == 'gut' else '#C9D6FF')
        out.append(f"""<div class="hrow"><span class="hlab">{esc(r['thema'])}</span>
        <div class="htrack"><div class="hfill" style="width:{w:.1f}%;background:{farbe}"></div><i class="tnorm" style="left:{nrm:.1f}%"></i></div>
        <span class="hval {klasse}">{de(r['med'], 2)} % · {de(r['n'])}{' · geringe Basis' if klein else ''}</span></div>""")
    return ''.join(out)

# 2-3 automatische Aussagen fuer 05
_gueltig = [r for r in THEMEN_ROWS if r['n'] >= 20]
_top_med = _gueltig[0] if _gueltig else None
_top_p90 = max(_gueltig, key=lambda r: r['p90']) if _gueltig else None
_schlecht = _gueltig[-1] if _gueltig else None
THEMEN_AUSSAGEN = []
if _top_med:
    THEMEN_AUSSAGEN.append(f"Stärkster Median: <b>{esc(_top_med['thema'])}</b> mit {de(_top_med['med'], 2)} % Median-ER über {de(_top_med['n'])} Beiträge.")
if _top_p90 and _top_p90 != _top_med:
    THEMEN_AUSSAGEN.append(f"Größte Ausreißer nach oben: <b>{esc(_top_p90['thema'])}</b> mit {de(_top_p90['p90'], 1)} % als 90. Perzentil.")
if _schlecht:
    THEMEN_AUSSAGEN.append(f"Schwächster Median (ab 20 Beiträgen): <b>{esc(_schlecht['thema'])}</b> mit {de(_schlecht['med'], 2)} %.")
THEMEN_TEXT = ''.join(f'<li>{a}</li>' for a in THEMEN_AUSSAGEN)
THEMEN_STICHPROBE = os.path.join(DATA, 'theme_accuracy.json')
if os.path.exists(THEMEN_STICHPROBE):
    _acc = json.load(open(THEMEN_STICHPROBE))
    ACC_TEXT = f"Klassenstichprobe: {_acc.get('richtig', 0)} von {_acc.get('n', 0)} geprüften Captions korrekt zugeordnet ({_acc.get('richtig', 0) / max(1, _acc.get('n', 1)) * 100:.0f} %)."
else:
    ACC_TEXT = ''


# Hashtags
tags = collections.Counter()
for p in posts:
    for t in re.findall(r'#(\w{3,30})', p.get('caption') or ''):
        tags[t.lower()] += 1
TOP_TAGS = tags.most_common(12)

# Wettbewerber
BRAND_DE = {'edeka': 'EDEKA', 'rewe': 'REWE', 'lidl': 'Lidl', 'aldi': 'ALDI', 'netto': 'Netto',
            'kaufland': 'Kaufland', 'penny': 'PENNY'}

# Ad-Zusammenfassung aus data/ads/*.json neu berechnen (nur eigene Marken-Seiten)
def _countdown(rows, key):
    c = collections.Counter(r.get(key) or 'kein CTA' for r in rows)
    return c.most_common()

ADS_PAGES = json.load(open(os.path.join(DATA, 'ads_pages.json')))
ads = {}
for _k, _allowed in {k: v for k, v in ADS_PAGES.items() if not k.startswith('_')}.items():
    _f = os.path.join(DATA, 'ads', f'{_k}.json')
    if not os.path.exists(_f):
        continue
    _all = json.load(open(_f)).get('rows') or []
    _own = [r for r in _all if (r.get('page_name') or '') in _allowed]
    ads[_k] = {
        'total': len(_all), 'own': len(_own),
        'pages': _countdown(_own, 'page_name'),
        'fmt': _countdown(_own, 'display_format'),
        'cta': _countdown(_own, 'cta_type'),
        'titles': [(r.get('title') or r.get('body') or '').strip()[:120] for r in _own],
        'starts': sorted(r.get('start_date') or '' for r in _own if r.get('start_date')),
        'newest': sorted((r.get('start_date') or '' for r in _own if r.get('start_date')), reverse=True),
    }

# ---- Weihnachts-Push / Advent-Check (REA-Scan, s. data/rea_advent.json) ----
try:
    REA = json.load(open(os.path.join(DATA, 'rea_advent.json')))
except Exception:
    REA = None

# ---- 04: Wettbewerb aus den Ad-Daten ableiten (keine Festwerte) ----
_APP_CTA = {'USE_APP', 'INSTALL_MOBILE_APP', 'USE_MOBILE_APP'}
_RECRU_RE = re.compile(r'karriere|job|ausbildung|bewerb|student|verkauf\s*\(?w/d|teilzeit|vollzeit', re.I)
_GEW_RE = re.compile(r'gewinn|gewinne|verlosung', re.I)

def _brand_rows(k):
    _f = os.path.join(DATA, 'ads', f'{k}.json')
    if not os.path.exists(_f):
        return []
    allowed = set(ADS_PAGES.get(k, []))
    return [r for r in (json.load(open(_f)).get('rows') or [])
            if (r.get('page_name') or '') in allowed]

ADS_BRAND = {}
for _k in BRAND_DE:
    _rows = _brand_rows(_k)
    _titles = [(r.get('title') or '') + ' ' + (r.get('body') or '') for r in _rows]
    ADS_BRAND[_k] = {
        'n': len(_rows),
        'recruiting': sum(1 for t in _titles if _RECRU_RE.search(t)) or
                      sum(1 for r in _rows if r.get('cta_type') == 'APPLY_NOW'),
        'app': sum(1 for r in _rows if (r.get('cta_type') or '') in _APP_CTA),
        'gewinn': sum(1 for t in _titles if _GEW_RE.search(t)),
        'video': sum(1 for r in _rows if r.get('display_format') == 'video'),
        'dco': sum(1 for r in _rows if r.get('display_format') in ('dco', 'dpa')),
        'whatsapp': sum(1 for r in _rows if r.get('cta_type') == 'WHATSAPP_MESSAGE'),
        'newsletter': sum(1 for t in _titles if 'newsletter' in t.lower()),
    }

def _brands(prop, minv=1):
    return [BRAND_DE[k] for k, v in ADS_BRAND.items() if v[prop] >= minv and v['n']]

_FRAME = []
_r = _brands('recruiting')
if _r:
    _FRAME.append(('Recruiting-Kampagnen', ' · '.join(f"{b} ({ADS_BRAND[[k for k, v in BRAND_DE.items() if v == b][0]]['recruiting']})" for b in _r)))
_a = _brands('app')
if _a:
    _FRAME.append(('App-Push', ' · '.join(f"{b} ({ADS_BRAND[[k for k, v in BRAND_DE.items() if v == b][0]]['app']})" for b in _a)))
_c = [k for k, v in ADS_BRAND.items() if (v['whatsapp'] or v['newsletter']) and v['n']]
if _c:
    _FRAME.append(('Community/Newsletter', ' · '.join(BRAND_DE[k] for k in _c)))
_d = _brands('dco')
if _d:
    _FRAME.append(('Angebots-/Produktfeeds (DCO/DPA)', ' · '.join(f"{b} ({ADS_BRAND[[k for k, v in BRAND_DE.items() if v == b][0]]['dco']})" for b in _d)))
_g = _brands('gewinn')
if _g:
    _FRAME.append(('Gewinnspiele', ' · '.join(f"{b} ({ADS_BRAND[[k for k, v in BRAND_DE.items() if v == b][0]]['gewinn']})" for b in _g)))
_fmt_all = collections.Counter()
for _k in BRAND_DE:
    for _r_ in _brand_rows(_k):
        _fmt_all[_r_.get('display_format') or 'ohne'] += 1
_AD_FMT = dict(FMT_DE, dco='DCO', dpa='DPA', image='Bild')
_FRAME.append(('Dominantes Format', ' · '.join(f"{_AD_FMT.get(f, f)} ({n})" for f, n in _fmt_all.most_common(3))))
FRAME_ROWS = ''.join(
    f'<tr><td>{esc(a)}</td><td class="num">{esc(b)}</td></tr>' for a, b in _FRAME)

def _fmt_brand(prop):
    return [BRAND_DE[k] for k, v in ADS_BRAND.items() if v[prop] and v['n']]

KONK_BULLETS = ''.join([
    '<li><b>Recruiting dominiert:</b> ' +
    (' · '.join(f"{BRAND_DE[k]} {ADS_BRAND[k]['recruiting']} von {ADS_BRAND[k]['n']}" for k in BRAND_DE if ADS_BRAND[k]['recruiting'])
     or 'keine') + ' eigene Anzeigen mit Job-/Ausbildungsbezug.</li>',
    '<li><b>Bewegtbild:</b> ' +
    (' · '.join(f"{BRAND_DE[k]} {ADS_BRAND[k]['video']} Video" for k in sorted(BRAND_DE, key=lambda x: -ADS_BRAND[x]['video']) if ADS_BRAND[k]['video'])
     or 'kaum') + ' (eigene Anzeigen im Sample).</li>',
    '<li><b>Dynamische Angebots-Feeds:</b> ' +
    (' · '.join(f"{BRAND_DE[k]} {ADS_BRAND[k]['dco']}" for k in sorted(BRAND_DE, key=lambda x: -ADS_BRAND[x]['dco']) if ADS_BRAND[k]['dco'])
     or 'kaum') + ' Anzeigen mit DCO/DPA.</li>',
    '<li><b>Community &amp; Newsletter:</b> ' +
    (' · '.join(BRAND_DE[k] for k in BRAND_DE if ADS_BRAND[k]['whatsapp'] or ADS_BRAND[k]['newsletter']) or 'keine') + ' nutzt direkten Kontaktaufbau als CTA.</li>',
    '<li><b>Gewinnspiele:</b> ' +
    (' · '.join(f"{BRAND_DE[k]} {ADS_BRAND[k]['gewinn']}" for k in sorted(BRAND_DE, key=lambda x: -ADS_BRAND[x]['gewinn']) if ADS_BRAND[k]['gewinn'])
     or 'keine') + ' mit Gewinnbezug im Sample.</li>',
    '<li><b>Tonalität:</b> Du-Ansprache, Emojis und kurze Claims durchgängig.</li>',
])

# Bilder holen
IMGMAP = {}
def dl(url, name):
    if not url:
        return ''
    path = os.path.join(IMG, name)
    if not (os.path.exists(path) and os.path.getsize(path) > 1000):
        ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
        subprocess.run(f"curl -s -A '{ua}' -e 'https://www.instagram.com/' -o '{path}' '{url}'",
                       shell=True, capture_output=True, timeout=30)
    return 'img/' + name if os.path.exists(path) and os.path.getsize(path) > 1000 else ''
for i, b in enumerate(best_posts[:15]):
    IMGMAP[b.get('image')] = dl(b.get('image'), f"b{i:02d}_{b['handle']}.jpg")
for i, b in enumerate(worst_posts[:15]):
    IMGMAP[b.get('image')] = dl(b.get('image'), f"w{i:02d}_{b['handle']}.jpg")
for i, b in enumerate(ueberflieger):
    IMGMAP[b.get('image')] = dl(b.get('image'), f"f{i:02d}_{b['handle']}.jpg")


# ---------------- Historie (Snapshots) ----------------
HIST_DIR = os.path.join(DATA, 'history')


def history_dates():
    if not os.path.isdir(HIST_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(HIST_DIR) if f.endswith('.json'))


def _load_snap(datum):
    return json.load(open(os.path.join(HIST_DIR, datum + '.json')))


def write_snapshot(beitraege):
    """Kompakter Tages-Snapshot: nur NEUE Beitraege + Follower, ohne Bilder."""
    os.makedirs(HIST_DIR, exist_ok=True)
    heute = dt.datetime.now(BERLIN).strftime('%Y-%m-%d')
    bekannt = set()
    for d in history_dates():
        if d == heute:
            continue
        for row in _load_snap(d).get('neu', []):
            bekannt.add(row[0])
    alt = _load_snap(heute) if heute in history_dates() else {'neu': [], 'follower': {}}
    alt_ids = {r[0] for r in alt.get('neu', [])}
    neu = []
    for q in beitraege:
        u = q.get('url')
        if not u or u in bekannt or u in alt_ids:
            continue
        neu.append([u, q['handle'], (q.get('likes') if q.get('likes_ok') else None),
                    q.get('comments'), (q.get('taken_at') or '')[:10], q.get('thema') or ''])
    snap = {'datum': heute,
            'follower': {a['handle']: a['followers'] for a in accounts},
            'neu': alt.get('neu', []) + neu}
    json.dump(snap, open(os.path.join(HIST_DIR, heute + '.json'), 'w'),
              ensure_ascii=False, separators=(',', ':'))


def _p90(vals):
    if not vals:
        return 0
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(0.9 * (len(v) - 1))))]


def hist_views():
    """Follower-Wachstum und Wochentrend. Erst ab zwei Snapshots."""
    dates = history_dates()
    if len(dates) < 2:
        return None, None
    snaps = [(d, _load_snap(d)) for d in dates]
    letzter = snaps[-1]
    alt_follower = snaps[-2][1].get('follower') or {}

    # --- Follower-Wachstum
    def delta(tage):
        ziel = dt.date.fromisoformat(letzter[0]) - dt.timedelta(days=tage)
        kand = [s for s in snaps if dt.date.fromisoformat(s[0]) <= ziel and s[1].get('follower')]
        if not kand:
            kand = [s for s in snaps[:-1] if s[1].get('follower')]
        if not kand:
            return None, None, None
        basis = kand[-1]
        b = basis[1]['follower']
        n = letzter[1].get('follower') or {}
        # nur Konten, die in BEIDEN Snapshots stehen (sonst Scheinbewegungen)
        gemein = [h for h in b if h in n]
        ges_b = sum(b[h] for h in gemein)
        ges_n = sum(n[h] for h in gemein)
        bewegt = sorted([(h, n[h] - b[h]) for h in gemein if n[h] != b[h]],
                        key=lambda x: -abs(x[1]))
        return (basis[0], ges_n - ges_b, bewegt[:6], ges_b)

    zeilen = []
    for tage, label in ((7, '7 Tage'), (30, '30 Tage')):
        r = delta(tage)
        if not r or r[0] is None:
            continue
        basis_datum, dsum, bewegt, base_ges = r
        pct = (dsum / base_ges * 100) if base_ges else 0
        sgn = '+' if dsum >= 0 else '\u2212'
        zeilen.append(f"""<div class="catrow"><div class="c1">Follower gesamt, {label} (seit {basis_datum})</div>
        <div class="c2">{sgn}{de(abs(dsum))}</div></div>
        <div class="catbar"><div style="width:{min(100, abs(pct) * 4):.0f}%;{'' if dsum >= 0 else 'background:#C9D6FF'}"></div></div>
        <div class="hint" style="margin:-4px 0 10px">{pct:+.2f} % · {de(base_ges)} Follower vorher</div>""")
    top = delta(7)
    if top and top[2]:
        zeilen.append('<div class="hint" style="margin-top:6px"><b>Größte Veränderungen (7 Tage):</b></div>')
        for h, dval in top[2]:
            if abs(dval) < 1:
                continue
            s2 = '+' if dval >= 0 else '\u2212'
            zeilen.append(f'<div class="catrow"><div class="c1">@{esc(h)}</div><div class="c2">{s2}{de(abs(dval))}</div></div>')
    growth = ''.join(zeilen) if zeilen else None

    # --- Wochentrend: Beitraege ueber alle Snapshots dedupliziert (Key Post-ID)
    alle = {}
    for _, s in snaps:
        for row in s.get('neu', []):
            alle[row[0]] = row
    wo = collections.defaultdict(lambda: [0, 0])
    for row in alle.values():
        if row[2] is None:
            continue
        try:
            dtag = dt.date.fromisoformat(row[4])
        except Exception:
            continue
        montag = dtag - dt.timedelta(days=dtag.weekday())
        slot = wo[montag]
        slot[0] += (row[2] or 0) + (row[3] or 0)
        slot[1] += 1
    if len(wo) < 2:
        return growth, None
    reihen = sorted(wo.items())[-8:]
    mx = max(v[0] / v[1] for _, v in reihen) or 1
    balken = []
    for montag, (inter, n) in reihen:
        val = inter / n if n else 0
        w = max(4, val / mx * 100)
        balken.append(f"""<div class="hrow"><span class="hlab">{montag.strftime('%d.%m.')}</span>
        <div class="htrack"><div class="hfill" style="width:{w:.1f}%"></div></div>
        <span class="hval">{de(val)} · {de(n)} Btr.</span></div>""")
    trend = (''.join(balken) + f'<p class="hint" style="margin-top:10px">{de(len(alle))} '
             f'eindeutige Beiträge aus {len(snaps)} Snapshots, ohne Fenster-Bias der letzten 12 Beiträge.</p>')
    return growth, trend


# ---------------- Chart-Bausteine ----------------
def svg_line(vals, labs, w=760, h=210):
    mx = max(vals) or 1
    pad_l, pad_b, pad_t = 8, 34, 26
    step = (w - pad_l * 2) / max(1, len(vals) - 1)
    pts = []
    for i, v in enumerate(vals):
        x = pad_l + i * step
        y = pad_t + (1 - v / mx) * (h - pad_t - pad_b)
        pts.append((x, y))
    poly = ' '.join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M{pts[0][0]:.1f},{h-pad_b:.1f} L" + ' L'.join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{h-pad_b:.1f} Z"
    dots = ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="#2A60FF"/>' for x, y in pts)
    lab = ''
    for i, (x, y) in enumerate(pts):
        if i % 2 == 0 or i == len(pts) - 1:
            anc = 'start' if i == 0 else ('end' if i == len(pts) - 1 else 'middle')
            lab += f'<text x="{x:.1f}" y="{h-12}" font-size="8" fill="#8A90A0" text-anchor="{anc}">{labs[i]}</text>'
    peak = max(range(len(vals)), key=lambda i: vals[i])
    px, py = pts[peak]
    ann = f'<text x="{px:.1f}" y="{py-9:.1f}" font-size="10" font-weight="600" fill="#2A60FF" text-anchor="middle">{de(vals[peak])}</text>'
    return f"""<div class="chartw"><svg viewBox="0 0 {w} {h}" width="100%" style="height:auto;display:block">
      <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#2A60FF" stop-opacity=".22"/><stop offset="100%" stop-color="#2A60FF" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="{area}" fill="url(#g1)"/>
      <polyline points="{poly}" fill="none" stroke="#2A60FF" stroke-width="1.5" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
      {dots}{ann}{lab}
    </svg></div>"""

def bars_v(items, valkey, labs, highlight=None, unit=''):
    mx = max([i[valkey] for i in items]) or 1
    out = []
    for i, it in enumerate(items):
        v = it[valkey]
        hh = max(6, v / mx * 132)
        blue = (highlight is not None and i == highlight)
        out.append(f"""<div class="bcol">{'<span class="bval">' + de(v, 1 if isinstance(v, float) else 0) + '</span>' if blue else ''}
          <div class="bbar" style="height:{hh:.0f}px;background:{'#2A60FF' if blue else '#C9D6FF'}"></div>
          <span class="blab">{esc(labs[i])}</span></div>""")
    return '<div class="barchart">' + ''.join(out) + '</div>'

def bars_h(rows, labkey, valkey, fmtf, maxn=12):
    mx = max([r[valkey] for r in rows[:maxn]]) or 1
    out = []
    for r in rows[:maxn]:
        w = max(4, r[valkey] / mx * 100)
        out.append(f"""<div class="hrow"><span class="hlab">{esc(r[labkey])}</span>
        <div class="htrack"><div class="hfill" style="width:{w:.1f}%"></div></div>
        <span class="hval">{fmtf(r[valkey])}</span></div>""")
    return ''.join(out)

def ring(pct, size=168, stroke=16):
    r = (size - stroke) / 2
    c = 2 * 3.14159 * r
    dash = c * pct / 100
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
      <circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="rgba(255,255,255,.32)" stroke-width="{stroke}"/>
      <circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="#fff" stroke-width="{stroke}" stroke-linecap="round"
        stroke-dasharray="{dash:.1f} {c-dash:.1f}" transform="rotate(-90 {size/2} {size/2})"/>
      <text x="50%" y="46%" text-anchor="middle" font-size="30" font-weight="700" fill="#fff">{pct:.0f} %</text>
      <text x="50%" y="63%" text-anchor="middle" font-size="12" fill="rgba(255,255,255,.9)">aktiv (30 Tage)</text></svg>"""

def kpi(label, value, sub, delta=''):
    d = f'<div class="delta">{esc(delta)}</div>' if delta else ''
    return f"""<div class="card kpi span2"><span class="arrow">↗</span>
      <div class="l">{esc(label)}</div><div class="k">{value}</div>
      <div class="delta grey">{esc(sub)}</div>{d}</div>"""

fmt_kpis = ''.join([
    kpi('Instagram-Profile', de(N_KONTEN), 'von 222 erfassten Konten'),
    kpi('Follower gesamt', de(N_FOLLOWER), 'über alle Profile'),
    kpi('Median-ER', de(OER_MED, 2) + ' %', f"Mittelwert {de(OER, 1)} % · Konten ab 500 Followern"),
    kpi('Analysierte Beiträge', de(N_POSTS), 'je Konto die letzten 12 Beiträge'),
])

# Tabellen
def t_profiles():
    out = []
    for i, a in enumerate(mov[:25]):
        out.append(f"""<tr><td>{i+1}</td>
        <td><a href="{esc(a['url'])}" target="_blank">@{esc(a['handle'])}</a><div class="sub2">{esc(a['nombre'])}</div></td>
        <td class="num">{de(a['followers'])}</td><td class="num strong">{a['er']:.1f} %</td>
        <td class="num">{a['er_med']:.2f} %</td><td class="num">{de(a['avg_likes'])}</td>
        <td class="num">{de(a['inter'])}</td><td class="num">{a['n']}</td><td class="num">{a['r30']}</td></tr>""")
    return ''.join(out)

# Phase 2: Ranking nach Median-ER, getrennt nach Groessensklassen
RANK_MIN_FOLLOWER = 500
SEGMENTS = [('< 2.000 Follower', lambda a: a['followers'] < 2000),
            ('2.000 bis 10.000 Follower', lambda a: 2000 <= a['followers'] <= 10000),
            ('> 10.000 Follower', lambda a: a['followers'] > 10000)]

def rank_pool(pred):
    return sorted([a for a in accounts
                   if a['followers'] >= RANK_MIN_FOLLOWER and a['n_valid'] >= MOV_MIN and pred(a)],
                  key=lambda a: -a['er_med'])

def t_rank(idx):
    rows = rank_pool(SEGMENTS[idx][1])
    out = []
    for i, a in enumerate(rows[:15]):
        out.append(f"""<tr><td>{i+1}</td>
        <td><a href="{esc(a['url'])}" target="_blank">@{esc(a['handle'])}</a><div class="sub2">{esc(a['nombre'])}</div></td>
        <td class="num">{de(a['followers'])}</td>
        <td class="num strong">{de(a['er_med'], 2)} %</td>
        <td class="num muted">{de(a['er'], 1)} %</td>
        <td class="num">{de(a['med_inter'])}</td>
        <td class="num">{a['n_valid']}</td><td class="num">{a['r30']}</td></tr>""")
    return ''.join(out)

def seg_kpi(idx):
    rows = rank_pool(SEGMENTS[idx][1])
    if not rows:
        return f'<div class="mini"><span>–</span>{esc(SEGMENTS[idx][0])}: kein Profil mit {MOV_MIN} Beiträgen</div>'
    return (f'<div class="mini"><span>@{esc(rows[0]["handle"])}</span>'
            f'{esc(SEGMENTS[idx][0])}: {de(rows[0]["er_med"], 2)} % Median-ER</div>')

SEG_KPIS = ''.join(seg_kpi(i) for i in range(3))
SEG_PANELS = ''.join(f"""<div class="segpanel" id="g{i}"{' style="display:none"' if i else ''}>
            <div class="tw"><table><thead><tr><th>#</th><th>Profil</th><th class="num">Follower</th>
              <th class="num">ER Median</th><th class="num muted">ER Ø</th>
              <th class="num">Interaktionen/Beitrag (Med.)</th><th class="num">Beiträge m. Like</th><th class="num">30 T.</th></tr></thead>
            <tbody>{t_rank(i)}</tbody></table></div>
            <p class="hint" style="margin-top:8px">{esc(SEGMENTS[i][0])}: {len(rank_pool(SEGMENTS[i][1]))} Profile im Ranking (ab {RANK_MIN_FOLLOWER} Followern, mindestens {MOV_MIN} Beiträge mit Like-Wert), Sortierung nach Median-ER, Top 15 gezeigt.</p>
          </div>""" for i in range(3))

def t_best():
    out = []
    for i, p in enumerate(best_posts[:15]):
        img = IMGMAP.get(p.get('image'), '')
        pl = esc(p.get('url') or '#')
        cell = f'<a href="{pl}" target="_blank"><img class="th" src="{esc(img)}" alt="" onerror="this.style.display=&#39;none&#39;"></a>' if img else ''
        out.append(f"""<tr><td>{i+1}</td><td>{cell}</td>
        <td><a href="https://www.instagram.com/{esc(p['handle'])}/" target="_blank">@{esc(p['handle'])}</a></td>
        <td class="cap">{esc((p.get('caption') or '')[:140])}</td>
        <td class="num strong">{de(p['likes'])}</td><td class="num">{p.get('comments') or 0}</td>
        <td class="num">{esc((p.get('taken_at') or '')[:10])}</td>
        <td><span class="pill2">{FMT_DE.get(p.get('kind'), esc(p.get('kind')))}</span></td>
        <td><a class="postlink" href="{pl}" target="_blank">Ansehen →</a></td></tr>""")
    return ''.join(out)

def t_worst():
    out = []
    for i, p in enumerate(worst_posts[:15]):
        img = IMGMAP.get(p.get('image'), '')
        pl = esc(p.get('url') or '#')
        cell = f'<a href="{pl}" target="_blank"><img class="th" src="{esc(img)}" alt="" onerror="this.style.display=&#39;none&#39;"></a>' if img else ''
        out.append(f"""<tr><td>{i+1}</td><td>{cell}</td>
        <td><a href="https://www.instagram.com/{esc(p['handle'])}/" target="_blank">@{esc(p['handle'])}</a></td>
        <td class="cap">{esc((p.get('caption') or '')[:140])}</td>
        <td class="num strong">{de(p['likes'])}</td><td class="num">{p.get('comments') or 0}</td>
        <td class="num">{esc((p.get('taken_at') or '')[:10])}</td>
        <td><span class="pill2">{FMT_DE.get(p.get('kind'), esc(p.get('kind')))}</span></td>
        <td><a class="postlink" href="{pl}" target="_blank">Ansehen →</a></td></tr>""")
    return ''.join(out)

def t_flieger():
    out = []
    for i, p in enumerate(ueberflieger):
        img = IMGMAP.get(p.get('image'), '')
        pl = esc(p.get('url') or '#')
        if img:
            cell = f'<a href="{pl}" target="_blank"><img class="th" src="{esc(img)}" alt="" onerror="this.style.display=&#39;none&#39;"></a>' 
        else:
            cell = f'<span class="ph">{FMT_DE.get(p.get("kind"), "Video")[:1]}</span>'
        out.append(f"""<tr><td>{i+1}</td><td>{cell}</td>
        <td><a href="https://www.instagram.com/{esc(p['handle'])}/" target="_blank">@{esc(p['handle'])}</a></td>
        <td class="cap">{esc((p.get('caption') or '')[:110])}</td>
        <td><span class="pill2">{FMT_DE.get(p.get('kind'), esc(p.get('kind')))}</span></td>
        <td class="num strong">{de(p['lift'], 1)}×</td>
        <td class="num">{de(p['likes'])}</td><td class="num">{p.get('comments') or 0}</td>
        <td class="num">{esc((p.get('taken_at') or '')[:10])}</td>
        <td><a class="postlink" href="{pl}" target="_blank">Ansehen →</a></td></tr>""")
    return ''.join(out)

def t_aktiv():
    out = []
    for i, a in enumerate(aktiv[:25]):
        out.append(f"""<tr><td>{i+1}</td>
        <td><a href="{esc(a['url'])}" target="_blank">@{esc(a['handle'])}</a><div class="sub2">{esc(a['nombre'])}</div></td>
        <td class="num">{a['r30']}</td><td class="num">{a['n']}</td>
        <td class="num">{de(a['inter'])}</td><td class="num">{de(a['followers'])}</td></tr>""")
    return ''.join(out)

# Wettbewerber-Tabelle
def t_ads():
    out = []
    for key in ['edeka', 'rewe', 'lidl', 'aldi', 'netto', 'kaufland', 'penny']:
        s = ads.get(key)
        if not s:
            continue
        fmt_str = ', '.join(f"{k} ({v})" for k, v in s.get('fmt', [])[:3])
        cta_str = ', '.join(k for k, v in s.get('cta', [])[:3])
        pages = ', '.join(k for k, v in s.get('pages', [])[:3])
        titles = [t for t in (s.get('titles') or []) if t][:2]
        neueste = (s.get('newest') or ['-'])[0][:10]
        out.append(f"""<tr><td><b>{esc(BRAND_DE.get(key, key))}</b></td>
        <td class="num">{s.get('own', 0)} / {s.get('total', 0)}</td>
        <td class="sub2">{esc(pages)}</td>
        <td class="sub2">{esc(fmt_str)}</td>
        <td class="sub2">{esc(cta_str)}</td>
        <td class="cap">{' · '.join(esc(t) for t in titles)}</td>
        <td class="num">{esc(neueste)}</td></tr>""")
    return ''.join(out)

def t_weihnacht():
    s = [r for r in REA['series'] if -84 <= r['offset'] <= 21]
    def cols(getter, unit=''):
        mx = max(max(getter(r)) for r in s) or 1
        out = []
        for r in s:
            v25, v26 = getter(r)
            h25 = max(3, v25 / mx * 118) if v25 else 3
            h26 = max(3, v26 / mx * 118) if v26 else 3
            lab = ('D+' if r['offset'] >= 0 else 'D') + str(r['offset'])
            v26s = (f"{v26:.1f}{unit}" if isinstance(v26, float) else str(v26)) if v26 else ''
            out.append(f"""<div class="bcol" style="min-width:30px">
          {'<span class="bval">' + v26s + '</span>' if v26s else ''}
          <div style="display:flex;align-items:flex-end;gap:3px;height:122px;width:100%;justify-content:center">
            <div style="width:44%;height:{h25:.0f}px;background:#C9D6FF;border-radius:4px 4px 0 0" title="2025: {v25}{unit}"></div>
            <div style="width:44%;height:{h26:.0f}px;background:#2A60FF;border-radius:4px 4px 0 0" title="2026: {v26}{unit}"></div>
          </div>
          <span class="blab">{lab}</span></div>""")
        return '<div class="barchart">' + ''.join(out) + '</div>'

    ads_chart = cols(lambda r: (r['ads_2025'], r['ads_2026']))
    trend_rows = [r for r in s if r.get('trend_2025') or r.get('trend_2026')]
    trend_chart = (cols(lambda r: (r.get('trend_2025') or 0, r.get('trend_2026') or 0), '×')
                   if trend_rows else '')
    A, B = REA['ads_total'], REA['ads_started_by_nov21']
    X = REA['copy_xmas_by_nov21']
    kpis = f"""<div class="miniRow" style="margin-bottom:16px">
      <div class="mini"><span>{de(A['2026'])} / {de(A['2025'])}</span>Anzeigen Meta Ad Library DE · Fenster 2026 (seit 20.10.) vs. Vorjahr (15.11.–31.12.)</div>
      <div class="mini"><span>{de(B['2026'])} / {de(B['2025'])}</span>gestartet bis 21.11. · {de(REA['ads_active_now_2026'])} davon jetzt aktiv</div>
      <div class="mini"><span>{de(X['2026'])} / {de(X['2025'])}</span>Anzeigen mit Weihnachts-Copy bis 21.11. (Weihnacht/Advent/Geschenk)</div>
    </div>"""
    bull = f"""<ul class="bul">
      <li><b>Weihnachts-Push startet später:</b> {esc(REA['site_seen'])} — erst 5 Anzeigen mit Weihnachts-Copy (Vorjahr zur gleichen Zeit: 10).</li>
      <li><b>Volumen aber höher:</b> {de(B['2026'])} gestartete Anzeigen bis 21.11. gegenüber {de(B['2025'])} im Vorjahr — EDEKA pumpt früh Reichweite, die Weihnachts-Botschaft kommt mit dem Adventskalender (23.11.).</li>
      <li><b>Vorjahres-Peaks:</b> {esc(' · '.join(REA['peaks']['2025']))} — dort wird dieses Jahr der Höhepunkt erwartet.</li>
      <li><b>Search-Ramp läuft noch nicht:</b> Google Trends „edeka" (DE) bei 0,3–1,1× zum Normalwert; der Großspike kam zuletzt erst nach Weihnachten (KW 29.12.2025: 10,3×).</li>
    </ul>"""
    return (kpis
            + '<p class="hint" style="margin-bottom:6px"><b>Anzeigen-Starts je Woche relativ zum 1. Dezember</b> — grau 2025, blau 2026 (D−14 = Woche bis 24.11.)</p>'
            + ads_chart
            + '<p class="hint" style="margin:14px 0 6px"><b>Google Trends „edeka" (DE) als Vielfaches des Normalwerts je Woche</b> — grau 2025 (Sep–Jan), blau 2026 (seit 22.09.)</p>'
            + trend_chart
            + bull)

WEI_CARD = ''
if REA:
    _stand_wei = dt.datetime.strptime(REA['stand'], '%Y-%m-%d').strftime('%d.%m.%Y')
    WEI_CARD = f"""<div class="card span6">
          <span class="arrow">↗</span>
          <h3>Weihnachts-Push · Advent-Check — Vorjahresvergleich</h3>
          <p class="hint">Reverse-Engineering des Weihnachtspushs (Meta Ad Library DE + Google Trends DE), Abfrage {_stand_wei}</p>
          {t_weihnacht()}
          <p class="hint" style="margin-top:12px"><b>Methodik:</b> Branchenschnitt Instagram 0,36 von 100 Followern (Rival IQ, Social Media Industry Benchmark Report 2025). {esc(REA['method'])}. Fenster {esc(REA['windows']['2025'])} (Vorjahr) vs. {esc(REA['windows']['2026'])} (laufendes Jahr); Status „alle" statt „aktiv", damit auch beendete Kampagnen mitgezählt werden. Die Vorjahres-Balken enthalten nur Anzeigen mit Impressionen im Fenster — Vergleiche gelten als Richtwert. Ad Library liefert keine Reichweiten- oder Kostenwerte.</p>
        </div>"""

fmt_cards = ''.join(f"""<div class="card kpi span2"><span class="arrow">↗</span>
  <div class="l">{esc(r['label'])}</div>
  <div class="k">{de(r['er_med'], 2)} %</div>
  <div class="delta grey">Median · Ø {de(r['er'], 1)} % · {de(r['n'])} Beiträge · {de(r['mean_likes'])} Likes</div></div>"""
  for r in fmt_rows)


CSS = """
@font-face{font-family:'Inter Tight';font-style:normal;font-weight:100 900;font-display:swap;src:url('fonts/inter-tight.woff2') format('woff2')}
*{box-sizing:border-box}
body{margin:0;background:#E7E4DC;color:#16150F;font:500 15px/1.45 'Inter Tight',Inter,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;padding:16px}
.app{min-height:100vh}
.main{background:#fff;border-radius:28px;padding:36px 40px 56px;max-width:1360px;margin:0 auto;min-width:0}
/* Navigation: Pill-Leiste */
.top{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;padding:0 0 6px}
.navleft{display:flex;align-items:center;gap:14px;flex-wrap:wrap;min-width:0}
.logo{flex:0 0 auto;width:52px;height:52px;border-radius:50%;background:#2A60FF;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:24px;letter-spacing:-.5px}
.tabs2{display:flex;gap:6px;flex-wrap:wrap;background:#F2F0EB;border-radius:999px;padding:6px;min-width:0}
.tab2{display:flex;flex-direction:column;justify-content:center;line-height:1.3;padding:8px 16px;border-radius:999px;font-size:14px;color:#3E3B33;cursor:pointer;font-weight:500;white-space:nowrap}
.tab2.on{background:#fff;color:#16150F;font-weight:600}
.tabd{font-size:11px;color:#6E6A60;font-weight:500;margin-top:2px}
.tab2.on .tabd{color:#6E6A60}
.tab2.dim{opacity:.6}
.meta{background:#F2F0EB;border-radius:999px;padding:11px 20px;font-size:14px;font-weight:600;color:#8C9AB3;white-space:nowrap}
/* Hero */
.hero{padding:40px 0 14px}
.eyb{display:block;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#6E6A60;margin-bottom:16px}
.h1{margin:0;font-size:84px;line-height:.98;font-weight:700;letter-spacing:-3.5px;color:#16150F;max-width:1160px}
/* Raster & Karten */
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:14px}
.card{background:#F2F0EB;border:0;box-shadow:none;border-radius:15px;padding:26px;position:relative;min-width:0}
.card .card{background:#fff}
.card.blue{background:#2A60FF;color:#fff;border-radius:15px;box-shadow:none}
.card h3{margin:0 0 8px;font-size:32px;line-height:1.12;font-weight:700;letter-spacing:-1px;padding-right:26px}
.card.span2 h3,.card.span3 h3{font-size:22px;letter-spacing:-.5px;padding-right:22px}
.card.blue h3{color:#fff;font-size:44px;line-height:1.05;letter-spacing:-1.5px}
.card .hint{margin:0 0 16px;font-size:14.5px;line-height:1.5;color:#6E6A60}
.card.blue .hint{color:rgba(255,255,255,.9)}
.arrow{display:none}
.muted{color:#6E6A60}
.ph{display:inline-flex;width:46px;height:46px;border-radius:8px;background:#E7E4DC;color:#6E6A60;align-items:center;justify-content:center;font-size:11px;font-weight:600}
.segtabs{margin-bottom:10px}
.span6{grid-column:span 6}.span4{grid-column:span 4}.span3{grid-column:span 3}.span2{grid-column:span 2}
/* KPI-Zahlen (Format-Kacheln) */
.kpi .l{display:block;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#6E6A60;margin-bottom:8px}
.kpi .k{display:block;font-size:76px;line-height:1;font-weight:700;letter-spacing:-2.5px;color:#16150F;margin:4px 0 8px}
.delta{font-size:13.5px;color:#2A60FF;font-weight:600}
.delta.grey{color:#6E6A60;font-weight:500}
/* Kennzahlen-Leiste auf blauen Karten */
.heroRow{display:flex;gap:26px;align-items:center;flex-wrap:wrap}
.heroStats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;flex:1;min-width:280px}
.heroStats.wide{grid-template-columns:repeat(4,1fr);gap:16px}
.hstat{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.28);border-radius:12px;padding:14px 16px}
.hstat .v{font-size:26px;font-weight:700;letter-spacing:-.8px;line-height:1.1}
.hstat .t{font-size:13px;color:rgba(255,255,255,.88);display:flex;align-items:center;gap:6px;font-weight:500}
.hstat .s{font-size:12px;color:rgba(255,255,255,.75);margin-top:4px}
.dot{width:8px;height:8px;border-radius:50%;background:#fff;display:inline-block;flex:0 0 auto}
.dot2{width:8px;height:8px;border-radius:50%;display:inline-block;flex:0 0 auto}
.ringbox{display:flex;align-items:center;justify-content:center;flex:0 0 auto}
@media(max-width:1150px){.heroStats.wide{grid-template-columns:repeat(2,1fr)}}
/* Saeulendiagramm */
.barchart{display:flex;align-items:flex-end;gap:12px;height:200px;padding-top:24px;overflow-x:auto}
.bcol{flex:1;min-width:56px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.bbar{width:100%;border-radius:7px 7px 0 0;background:#E7E4DC}
.bval{font-size:12px;font-weight:700;color:#2A60FF;margin-bottom:6px}
.blab{font-size:12px;color:#6E6A60;margin-top:7px;text-align:center;line-height:1.25;height:auto;max-height:46px;word-break:break-word;hyphens:auto}
/* Horizontale Balken mit Wert-Pill */
.hrow{display:grid;grid-template-columns:170px minmax(0,1fr) minmax(96px,auto);align-items:center;gap:12px;margin:9px 0}
.hlab{font-size:14.5px;font-weight:500;color:#3E3B33}
.htrack{position:relative;background:#fff;height:14px;border-radius:7px;overflow:hidden}
.hfill{height:100%;background:#2A60FF;border-radius:7px;min-width:6px}
.tnorm{position:absolute;top:0;bottom:0;width:2px;background:#16150F}
.hval{justify-self:end;text-align:center;background:#fff;border-radius:999px;padding:5px 12px;font-size:13px;font-weight:700;color:#16150F;white-space:nowrap;font-variant-numeric:tabular-nums}
.hval.gut{background:#2A60FF;color:#fff;box-shadow:none}
.hval.schwach{background:#C9D6FF;color:#16150F;box-shadow:none}
.hval.klein{color:#6E6A60;font-weight:600}
/* Kategorie-Balken */
.catrow{display:grid;grid-template-columns:1fr auto;gap:6px;margin-bottom:5px;font-size:14.5px}
.catrow .c1{display:flex;align-items:center;gap:8px;color:#3E3B33}
.catrow .c2{font-weight:700;font-variant-numeric:tabular-nums;color:#16150F}
.catbar{grid-column:1/-1;height:8px;background:#fff;border-radius:4px;overflow:hidden;margin-bottom:14px}
.catbar div{height:100%;background:#2A60FF;border-radius:4px}
/* Mini-Kacheln */
.miniRow{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
.mini{background:#fff;border:0;border-radius:15px;padding:16px 18px;font-size:14px;color:#6E6A60;line-height:1.4}
.mini span{display:block;font-size:24px;font-weight:700;letter-spacing:-.7px;color:#16150F;margin-bottom:4px}
/* Verfuegbarkeit */
.avail{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.avail .ok,.avail .no{border-radius:15px;padding:20px 22px;font-size:14.5px;line-height:1.5}
.avail .ok{background:#fff}
.avail .no{background:#E7E4DC}
.avail b{display:block;margin-bottom:10px;font-size:15px;font-weight:700}
.avail .ok b{color:#2A60FF}
.avail .no b{color:#16150F}
.avail ul{margin:0;padding-left:18px;color:#3E3B33}
.avail li{margin:6px 0}
/* Listen */
.bul{margin:0;padding-left:20px;font-size:15px;line-height:1.45;color:#3E3B33}
.bul li{margin:10px 0}
.steps{margin:0;padding-left:22px;font-size:15px;line-height:1.45;color:#3E3B33}
.steps li{margin:11px 0}
/* Hashtags */
.tagwrap{display:flex;flex-wrap:wrap;gap:8px}
.tag{background:#fff;color:#16150F;font-size:13px;font-weight:600;padding:6px 12px;border-radius:999px}
/* Anzeigen */
.adgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.adcard{border:0;border-radius:15px;overflow:hidden;background:#fff;box-shadow:none}
.adimg{position:relative;display:block;line-height:0}
.adimg img{width:100%;height:172px;object-fit:cover;background:#E7E4DC;display:block}
.adfmt{position:absolute;left:12px;top:12px;background:#2A60FF;color:#fff;font-size:11px;font-weight:700;padding:5px 11px;border-radius:999px;text-transform:uppercase;letter-spacing:.5px}
.adbody{padding:16px 18px 18px}
.adbrand{font-weight:700;font-size:15px;color:#16150F;margin-bottom:6px}
.adbrand span{color:#6E6A60;font-weight:500}
.adlabel{font-size:13px;letter-spacing:1px;font-weight:600;text-transform:uppercase;color:#6E6A60;margin:12px 0 5px}
.adhook{font-size:15px;font-weight:600;color:#16150F;line-height:1.4}
.adwhy{font-size:14.5px;color:#3E3B33;line-height:1.5}
.admeta{font-size:13px;color:#6E6A60;margin-top:10px;line-height:1.5}
.adlink{font-size:13px;font-weight:600;display:inline-block;margin-top:8px}
.postlink{font-size:13px;font-weight:600;white-space:nowrap}
/* Tabs & Tabellen */
.tabs{display:flex;gap:8px;margin:0 0 6px;flex-wrap:wrap}
.tab{background:#fff;border:0;color:#3E3B33;padding:9px 16px;border-radius:999px;cursor:pointer;font-size:13.5px;font-weight:600}
.tab.on{background:#2A60FF;color:#fff}
table{width:100%;border-collapse:collapse;font-size:14.5px}
table.compact td{padding:9px 7px}
th,td{padding:11px 9px;text-align:left;border-bottom:1px solid #E7E4DC;vertical-align:middle}
th{font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:#6E6A60;font-weight:600;background:transparent;border-bottom:1px solid #E1DED6}
tr:hover td{background:rgba(255,255,255,.65)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.strong{font-weight:700;color:#16150F}
.sub2{font-size:13px;color:#6E6A60}
.cap{color:#3E3B33;font-size:14px;max-width:380px}
.pill2{display:inline-block;background:#fff;color:#16150F;font-size:13px;padding:5px 11px;border-radius:999px;font-weight:600;white-space:nowrap}
.th{width:46px;height:46px;object-fit:cover;border-radius:7px;background:#E7E4DC;display:block}
a{color:#2A60FF;text-decoration:none}
a:hover{text-decoration:underline}
.footer{margin-top:26px;background:#F2F0EB;border:0;border-radius:15px;padding:26px 28px;font-size:14px;line-height:1.65;color:#6E6A60}
@media(max-width:1250px){.grid{grid-template-columns:repeat(2,1fr)}.span6,.span4,.span3,.span2{grid-column:span 2}.avail{grid-template-columns:1fr}}
@media(max-width:760px){.grid{grid-template-columns:1fr}.span6,.span4,.span3,.span2{grid-column:span 1}.hrow{grid-template-columns:110px minmax(0,1fr) auto;gap:8px}}
"""


JS = """
function sec(id, el){
  document.querySelectorAll('.sec').forEach(s=>s.style.display='none');
  document.getElementById(id).style.display='block';
  document.querySelectorAll('.tab2').forEach(t=>t.classList.toggle('on', t.getAttribute('data-s')===id));
  var on=document.querySelector('.tab2.on'); if(on&&on.scrollIntoView){on.scrollIntoView({block:'nearest',inline:'center',behavior:'smooth'});}
  window.scrollTo(0,0);
}
(function(){
  function upd(){var n=document.querySelector('.top'); if(n) n.classList.toggle('scrolled', window.scrollY>20);}
  window.addEventListener('scroll',upd,{passive:true}); document.addEventListener('DOMContentLoaded',upd);
  document.addEventListener('DOMContentLoaded',function(){var t=document.querySelector('.tabs2'); if(!t) return;
    function f(){t.classList.toggle('end', t.scrollLeft+t.clientWidth>=t.scrollWidth-4);} t.addEventListener('scroll',f,{passive:true}); f();});
})();
function tab(id, el){
  document.querySelectorAll('.panel').forEach(p=>p.style.display='none');
  var t = document.getElementById(id);
  t.style.display='block';
  document.querySelectorAll('.tabs .tab').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  var st = t.querySelector('.segtabs');
  if (st){
    st.querySelectorAll('.tab').forEach((b,i)=>b.classList.toggle('on', i===0));
    t.querySelectorAll('.segpanel').forEach((s,i)=>s.style.display = i===0 ? 'block' : 'none');
  }
}
function seg(id, el){
  var panel = el.closest('.panel');
  var bar = el.closest('.segtabs');
  panel.querySelectorAll('.segpanel').forEach(s=>s.style.display='none');
  document.getElementById(id).style.display='block';
  bar.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));
  el.classList.add('on');
}
"""


# ---------------- Top-Werbeanzeigen ----------------
TOP_ADS = json.load(open(os.path.join(DATA, 'top_ads.json'))) if os.path.exists(os.path.join(DATA, 'top_ads.json')) else []
HOOFS = [
 ("Gewinne 15.000 € für dein Zuhause-Upgrade",
  "Konkreter Geldwert direkt im ersten Frame, dazu die Gewinnmechanik als Lead-Magnet (Teilnahme nur mit Newsletter-Anmeldung). Der Preisnutzen ist in unter einer Sekunde verstanden — genau das braucht es im Feed."),
 ("Deine Meinung zählt: Werde Teil der WhatsApp-Community",
  "Humor statt Produktwerbung: extremer Nahschnitt und Selfie-Ästhetik wirken wie ein Freundes-Post, nicht wie eine Anzeige. Der Gag kommt zuerst, die Community-Werbung danach. Der in der Ad Library hinterlegte CTA lautet DOWNLOAD, die Anzeige selbst führt auf die WhatsApp-Community (Meta vergibt hier einen Standard-CTA)."),
 ("Herbstlicher Gnocchi-Salat · Ausgewogene Ernährung",
  "Nutzen-Content statt Werbung: das Rezept hält die Watch-Time hoch und positioniert den Anbieter als Kompetenzquelle. Saisonbezug schafft Aktualität, die Produktbotschaft (Tiefpreis) kann weich eingebaut werden."),
 ("POV: Du willst den günstigsten Preis",
  "Meme-Format „POV“ mit KI-Gesicht spricht den zentralen Kundenwunsch wörtlich aus. Gleichzeitig Abgrenzungskampagne gegen Coupon-Apps — eine klare Haltung, die sich ohne Rabattverlust erzählen lässt."),
 ("MASSIV REDUZIERT",
  "Absurd-humorvolle Szene (Schokoladenfontäne) stoppt den Scroll, der Claim ist als eigene Kampagnen-Wortmarke wiedererkennbar. Der konkrete Rabatt (20 % Oktober) liefert Dringlichkeit und Anlass zum Klick."),
 ("Wenn ich was Neues anfange",
  "Echtes Gesicht und echter Satz statt Stellenanzeige: Testimonials machen die Ausbildung glaubwürdig und ansprechbar für eine junge Zielgruppe. Der CTA (bewerben) ist klar, aber erst nach der Identifikation."),
 ("Lauras Sidequest · powered by REWE GO",
  "Series-Branding („Sidequest“) bindet wie eine Sendung statt einer Einzelanzeige — Zuschauer kommen wegen der Figur wieder. Das Produkt (Snack-Aktion) wird in die Handlung eingebettet, nicht beworben."),
 ("Bewirb dich für einen Job im Verkauf",
  "Zwei Zeilen, ein Gesicht, eine Botschaft: maximale Klarheit auf kleinstem Raum, Marken-Blau als Wiedererkennung. Menschen statt Textwand senken die Hürde zur Bewerbung."),
]
ad_cards = []
for i, ad in enumerate(TOP_ADS):
    if i >= len(HOOFS):
        break
    hook, why = HOOFS[i]
    imgpath = f"img/ad{i}.jpg"
    meta = f"{ad.get('brand')} · {ad.get('page')} · {ad.get('fmt')} · aktiv seit {ad.get('start')} ({ad.get('age')} Tage) · CTA: {ad.get('cta')}"
    adlink = ad.get('url') or '#'
    ad_cards.append(f"""
    <div class="adcard">
      <a class="adimg" href="{esc(adlink)}" target="_blank"><img src="{esc(imgpath)}" alt="" onerror="this.style.display='none'"><span class="adfmt">{esc(ad.get('fmt'))}</span></a>
      <div class="adbody">
        <div class="adbrand">{esc(ad.get('brand'))} <span>· {esc(ad.get('page'))}</span></div>
        <div class="adlabel">HOOK</div>
        <div class="adhook">{esc(hook)}</div>
        <div class="adlabel">WARUM ES FUNKTIONIERT</div>
        <div class="adwhy">{esc(why)}</div>
        <div class="admeta">{esc(meta)}</div>
        <a class="adlink" href="{esc(adlink)}" target="_blank">Anzeige in der Meta Ad Library ansehen →</a>
      </div>
    </div>""")
ad_grid = '<div class="adgrid">' + ''.join(ad_cards) + '</div>'

# ---------------- Tabellen-Vollmarken (Marker nie innerhalb von tbody) ----------------
TW_TOP = ('<div class="tw"><table><thead><tr><th>#</th><th>Media</th><th>Profil</th><th>Text</th>'
          '<th class="num">Likes</th><th class="num">Komment.</th><th class="num">Datum</th>'
          '<th>Format</th><th>Link</th></tr></thead><tbody>' + t_best() + '</tbody></table></div>')
TW_WORST = ('<div class="tw"><table><thead><tr><th>#</th><th>Media</th><th>Profil</th><th>Text</th>'
            '<th class="num">Likes</th><th class="num">Komment.</th><th class="num">Datum</th>'
            '<th>Format</th><th>Link</th></tr></thead><tbody>' + t_worst() + '</tbody></table></div>')
TW_AKTIV = ('<div class="tw"><table><thead><tr><th>#</th><th>Profil</th><th class="num">Beiträge 30 T.</th>'
            '<th class="num">Beiträge ges.</th><th class="num">Interaktionen</th>'
            '<th class="num">Follower</th></tr></thead><tbody>' + t_aktiv() + '</tbody></table></div>')
TW_FLIEGER = ('<div class="tw"><table><thead><tr><th>#</th><th>Media</th><th>Profil</th><th>Text</th>'
              '<th>Format</th><th class="num">Lift</th><th class="num">Likes</th><th class="num">Komment.</th>'
              '<th class="num">Datum</th><th>Link</th></tr></thead><tbody>' + t_flieger() +
              '</tbody></table></div>')
TW_ADS = ('<div class="tw"><table><thead><tr><th>Marke</th><th class="num">Anzeigen im Sample / Treffer</th>'
          '<th>Werbeanzeigen-Seiten</th><th>Formate</th><th>CTA-Typen</th><th>Beispiel-Nachrichten</th>'
          '<th class="num">Neuester Start</th></tr></thead><tbody>' + t_ads() + '</tbody></table></div>')
TW_FRAME = '<div class="tw"><table class="compact"><tbody>' + FRAME_ROWS + '</tbody></table></div>'


# ---------------- 00 · Was jetzt tun (Klartext-Empfehlungen, automatisch aus den Daten) ----------------
def _z(v, dec=1):
    return de(v, dec)

def _mal(a, b):
    if not b:
        return '–'
    f = a / b
    return (f'{f:.0f}×' if f >= 3 else f'{f:.1f}×'.replace('.', ','))

# Basis = normaler Beitrag (Median-ER aller Beitraege mit Like-Wert) - gleiche Masseinheit wie Themen/Formate/Uhrzeiten
_ALL_ER = [((q.get('likes') or 0) + (q.get('comments') or 0)) / q['followers'] * 100 for q in posts if q.get('likes_ok') and q['followers']]
POST_MED = statistics.median(_ALL_ER) if _ALL_ER else OER_MED

_TH_OK = [r for r in THEMEN_ROWS if r['n'] >= 20 and r['thema'] != 'Sonstiges']
_TH_BEST = _TH_OK[:2] if len(_TH_OK) >= 2 else _TH_OK
_TH_WORST = _TH_OK[-1] if _TH_OK else None
_TH_SUM = sum(r['n'] for r in _TH_OK) or 1

def _empf(r):
    if r['thema'] == 'Sonstiges':
        return ('grey', 'Thema schärfen')
    if r['med'] >= POST_MED:
        return ('green', 'Mehr davon')
    if r['med'] >= POST_MED * 0.7:
        return ('amber', 'Aufpeppen')
    return ('red', 'Umbauen')

_SCHWACH = [r for r in _TH_OK if _empf(r)[0] != 'green']
_SCHWACH_PCT = sum(r['n'] for r in _SCHWACH) / max(1, sum(r['n'] for r in THEMEN_ROWS)) * 100

# Format
_FMT_BY = {r['label']: r for r in fmt_rows}
_FMT_BASE = FMT_MED_BEST
_FMT_BONUS_LAB = FL_FMT.most_common(1)[0][0] if FL_FMT else None
_FMT_BONUS = _FMT_BY.get(_FMT_BONUS_LAB) if _FMT_BONUS_LAB else None
_FMT_BONUS_N = FL_FMT.most_common(1)[0][1] if FL_FMT else 0

# Thema x Format: beste Kombinationen
_COMBOS = []
for (_t, _k), _vals in _MATRIX.items():
    if len(_vals) >= 10 and _t not in ('Sonstiges', 'nicht zugeordnet'):
        _COMBOS.append({'thema': _t, 'fmt': FMT_DE.get(_k, _k), 'med': statistics.median(_vals), 'n': len(_vals)})
_COMBOS.sort(key=lambda c: -c['med'])
_COMBOS = _COMBOS[:3]

# Zeit
_HR_BEST = sorted(HR_ROWS, key=lambda r: -r['med'])[:2]
_HR_VOLL = max(HR_ROWS, key=lambda r: r['n']) if HR_ROWS else None
_WD_BEST = WD_ORD[0] if WD_ORD else None
_WD_WORST = WD_ORD[-1] if WD_ORD else None

# Wettbewerb
_ED = ADS_BRAND.get('edeka', {'dco': 0, 'recruiting': 0, 'n': 0})
_KONK = {k: v for k, v in ADS_BRAND.items() if k != 'edeka' and v.get('n')}
_DCO_TOP = max(_KONK, key=lambda k: _KONK[k]['dco']) if _KONK else None
_REC_TOP = max(_KONK, key=lambda k: _KONK[k]['recruiting']) if _KONK else None

# --- Verständlichkeit: jede Zahl mit Urteil und Vergleich ---
BENCH_ER = 0.36   # Rival IQ, 2025 Social Media Industry Benchmark Report: Median-Engagement-Rate Instagram, alle Branchen
BENCH_QUELLE = 'Rival IQ, Benchmark-Report 2025'

def _rel(v, base=None):
    """Vergleich mit einem normalen Beitrag, in Worten."""
    base = base or POST_MED
    if not base:
        return ('info', '–')
    f = v / base
    if f >= 1.15:
        return ('gut', (f'{f:.0f}× so gut' if f >= 2.95 else f'{f:.1f}× so gut'.replace('.', ',')))
    if f <= 0.87:
        return ('schwach', f'{(1 - f) * 100:.0f} % schwächer')
    return ('info', 'wie normal')

def _bruch(anteil):
    if anteil <= 0:
        return '0'
    n = round(1 / anteil)
    return f'1 von {n}' if n >= 2 else f'{anteil * 100:.0f} %'

ZIEL_DE = {'Umsatz': 'Umsatz', 'Frequenz': 'Frequenz', 'Preiswahrnehmung': 'Preiswahrnehmung'}
def _ziele(lst):
    return '<div class="ziele"><span class="zlbl">Zahlt ein auf</span>' + ''.join(f'<span class="ziel">{esc(z)}</span>' for z in lst) + '</div>'

def _fx(v):
    f = v / POST_MED if POST_MED else 0
    return (f'{f:.0f}×' if f >= 2.95 else f'{f:.1f}×'.replace('.', ','))

def _evid(n, note=''):
    if n is None:
        return ('begrenzt', 'Begrenzt', note or 'kleine Stichprobe')
    if n >= 100:
        return ('stark', 'Stark', f'{de(n)} Beiträge je Gruppe')
    if n >= 30:
        return ('mittel', 'Mittel', f'{de(n)} Beiträge je Gruppe')
    return ('begrenzt', 'Begrenzt', f'nur {de(n)} Beiträge')

def _hour(q):
    ts = q.get('taken_at')
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(BERLIN).hour
    except Exception:
        return None

def _er(q):
    return ((q.get('likes') or 0) + (q.get('comments') or 0)) / q['followers'] * 100 if q.get('followers') else 0

def _beispiel(pred, txt=''):
    pool = [q for q in posts if q.get('likes_ok') and (q.get('followers') or 0) >= 1000 and pred(q) and _er(q) <= POST_MED * 8]
    if not pool:
        return ''
    q = max(pool, key=_er)
    _acc = _acc_idx.get(q['handle']) or {}
    _inter = (q.get('likes') or 0) + (q.get('comments') or 0)
    _sonst = f" statt sonst rund {de(_acc.get('med_inter'))}" if _acc.get('med_inter') else ''
    return (f'<a class="hbsp" href="{esc(q.get("url") or "#")}" target="_blank" rel="noopener">'
            f'<b>@{esc(q["handle"])}</b> · {esc((q.get("taken_at") or "")[:10])} · {FMT_DE.get(q.get("kind"), esc(q.get("kind") or ""))}'
            f'{(" · " + txt) if txt else ""}<br>{de(_inter)} Reaktionen{_sonst} <span>Post ansehen →</span></a>')

_AUFW = {'gering': ('gering', 'Gering'), 'mittel': ('mittel', 'Mittel'), 'hoch': ('hoch', 'Hoch')}

def _hebel(nr, titel, warum, tun, wer, ziele, span=3, wirkung='', wcls='info', bars=(), kurz='', big='', bigsub='', akt='',
           bedeutung='', beispiel='', messung='', evid=None, aufwand='mittel', wirk=1.0):
    ev = evid or ('begrenzt', 'Begrenzt', '')
    au = _AUFW.get(aufwand, _AUFW['mittel'])
    score = {'stark': 3, 'mittel': 2, 'begrenzt': 1}[ev[0]] + (3 if wirk >= 3 else 2 if wirk >= 1.8 else 1) - {'gering': 0, 'mittel': 1, 'hoch': 2}[au[0]]
    rows = []
    if bars:
        mx = max(b[2] for b in bars[:2]) or 1
        for _lab, _wert, _val, _good in bars[:2]:
            _wp = max(3, min(100, _val / mx * 100))
            rows.append(f'<div class="hb"><div class="hbh"><span>{_lab}</span><b>{_wert}</b></div>'
                        f'<div class="hbt"><div class="hbf{"" if _good else " s"}" style="width:{_wp:.0f}%"></div></div></div>')
    def html(rang):
        return f"""<div class="ht">
          <div class="hth"><span class="hnr">{rang}</span><span class="htz">Ziel: {' · '.join(ziele)}</span></div>
          <div class="htt">{kurz or titel}</div>
          <div class="htn"><b>{big or wirkung}</b><span>{bigsub}</span></div>
          <div class="hbs">{''.join(rows)}</div>
          <div class="hta">{akt}</div>
          <div class="hev"><span class="dot d-{ev[0]}"></span>Evidenz {ev[1].lower()} · Aufwand {au[1].lower()}</div>
          <details class="htd"><summary>Warum &amp; wie?</summary>
            <dl>
              <dt>Beobachtung</dt><dd>{warum}</dd>
              <dt>Bedeutung</dt><dd>{bedeutung}</dd>
              <dt>Empfehlung</dt><dd>{tun}</dd>
              {f'<dt>Beispiel</dt><dd>{beispiel}</dd>' if beispiel else ''}
              <dt>Erfolgsmessung</dt><dd>{messung}</dd>
              <dt>Belastbarkeit</dt><dd>Evidenz {ev[1].lower()} ({esc(ev[2])}). Aufwand: {au[1].lower()} (Einschätzung). Zusammenhang, kein Beweis für Ursache.</dd>
            </dl></details>
        </div>"""
    return (score, html)

_HEBEL = []
if _TH_BEST and _TH_WORST:
    _b = _TH_BEST[0]; _w = _TH_WORST
    _preis = 'Angebot' in _w['thema']
    _HEBEL.append(_hebel(1,
        ('Preis beweisen – mit Menschen statt Preisschildern' if _preis
         else f"{esc(_w['thema'])} umbauen – mehr {' &amp; '.join(esc(r['thema']) for r in _TH_BEST)}"),
        f"Reine <b>{esc(_w['thema'])}</b>-Posts laufen <b>{_rel(_w['med'])[1]}</b> als ein normaler Beitrag. "
        f"<b>{esc(_b['thema'])}</b> läuft <b>{_rel(_b['med'])[1]}</b> – {_mal(_b['med'], _w['med'])} so gut wie reine Preis-Posts.",
        ("Den Preis nicht weglassen, sondern beweisen: jemand aus dem Markt zeigt den Kassenbon, erklärt den Preishelden oder erzählt die Geschichte hinter dem Produkt. „Rechne nach“ wird zum Post."
         if _preis else f"{esc(_w['thema'])} mit Gesichtern, Humor oder Herkunft erzählen."),
        'Für alle Märkte &amp; die Zentrale', ['Preiswahrnehmung', 'Frequenz'],
        bedeutung='Menschen schaffen Nähe und Glaubwürdigkeit – genau das braucht eine Preisbotschaft. Ob Preis und Menschen <b>zusammen</b> besser laufen, ist noch nicht gemessen: Die Themen-Erkennung ordnet jedem Post nur ein Thema zu.', beispiel=_beispiel(lambda q: q.get('thema') == _b['thema'], esc(_b['thema'])), messung='Neue Preis-Posts mit Gesicht als eigene Gruppe markieren und nach 4 Wochen mit reinen Preis-Posts vergleichen (Reaktionen pro 100 Follower).', evid=_evid(min(_b['n'], _w['n'])), aufwand='mittel', wirk=_b['med'] / _w['med'] if _w['med'] else 1,
        kurz=('Preis beweisen – mit Menschen' if _preis else f"{esc(_w['thema'])} umbauen"), big=_mal(_b['med'], _w['med']), bigsub=f"{esc(_b['thema'])} vs. {esc(_w['thema'])}", akt=('Preise mit Gesichtern aus dem Markt zeigen.' if _preis else 'Mit Gesichtern, Humor oder Herkunft erzählen.'),
        wirkung=f'{_mal(_b["med"], _w["med"])} Unterschied', wcls=_rel(_b["med"])[0],
        bars=[(esc(_b["thema"]), _rel(_b["med"])[1], _b["med"], _rel(_b["med"])[0] == 'gut'),
              (esc(_w["thema"]), _rel(_w["med"])[1], _w["med"], _rel(_w["med"])[0] == 'gut')]))
if _FMT_BASE and _FMT_BONUS:
    _HEBEL.append(_hebel(2,
        f"{esc(_FMT_BASE['label'])} als Standard, {esc(_FMT_BONUS['label'])} als Bonus",
        f"Ein <b>{esc(_FMT_BASE['label'])}</b> läuft <b>{_rel(_FMT_BASE['er_med'])[1]}</b> – das verlässlichste Format. "
        f"<b>{esc(_FMT_BONUS['label'])}</b> laufen meist <b>{_rel(_FMT_BONUS['er_med'])[1]}</b>, aber <b>{_FMT_BONUS_N} der {len(ueberflieger)} viralen Posts</b> waren {esc(_FMT_BONUS['label'])}.",
        f"Den Großteil als {esc(_FMT_BASE['label'])} planen. {esc(_FMT_BONUS['label'])} gezielt für Humor &amp; Team – der Glückstreffer mit dem größten Potenzial.",
        'Für alle Märkte', ['Frequenz'],
        bedeutung='Karussells liefern am verlässlichsten überdurchschnittliche Reaktionen. Reels streuen stark: meist schwächer, aber mit den größten Ausreißern nach oben.', beispiel=_beispiel(lambda q: q.get('kind') == _FMT_BASE['key']), messung=f"Anteil {esc(_FMT_BASE['label'])} an allen Posts und deren Reaktionen pro 100 Follower, monatlich im Dashboard (Tab 02).", evid=_evid(min(_FMT_BASE['n'], _FMT_BONUS['n'])), aufwand='gering', wirk=_FMT_BASE['er_med'] / POST_MED if POST_MED else 1,
        kurz=f"{esc(_FMT_BASE['label'])} als Standard", big=_fx(_FMT_BASE['er_med']), bigsub=f"{esc(_FMT_BASE['label'])} vs. normaler Post", akt=f"Großteil als {esc(_FMT_BASE['label'])}, {esc(_FMT_BONUS['label'])} für Team &amp; Humor.",
        wirkung=_rel(_FMT_BASE['er_med'])[1], wcls=_rel(_FMT_BASE['er_med'])[0],
        bars=[(esc(_FMT_BASE['label']), _rel(_FMT_BASE['er_med'])[1], _FMT_BASE['er_med'], _rel(_FMT_BASE['er_med'])[0] == 'gut'),
              (esc(_FMT_BONUS['label']), _rel(_FMT_BONUS['er_med'])[1], _FMT_BONUS['er_med'], _rel(_FMT_BONUS['er_med'])[0] == 'gut')]))
if _COMBOS:
    _chips = ''.join(f'<span class="combo"><span><b>{esc(c["thema"])}</b> als {esc(c["fmt"])}</span><i class="{_rel(c["med"])[0]}">{_rel(c["med"])[1]}</i></span>' for c in _COMBOS)
    _HEBEL.append(_hebel(3,
        'Die Gewinner-Kombinationen als Vorlagen bauen',
        f"Diese Mischungen aus Thema und Format laufen am besten – verglichen mit einem normalen Beitrag.",
        'Für jede Kombination eine fertige Vorlage an die Märkte geben – dann muss nicht jeder Markt das Rad neu erfinden.',
        'Zentrale → Märkte', ['Frequenz', 'Umsatz'],
        bedeutung='Diese Mischungen funktionieren bereits in einzelnen Märkten. Vorlagen machen den Erfolg für alle wiederholbar.', beispiel=_beispiel(lambda q: q.get('thema') == _COMBOS[0]['thema'] and FMT_DE.get(q.get('kind')) == _COMBOS[0]['fmt'], f"{esc(_COMBOS[0]['thema'])} als {esc(_COMBOS[0]['fmt'])}"), messung='Reaktionen der Vorlagen-Posts im Vergleich zum normalen Beitrag und Zahl der Märkte, die sie nutzen.', evid=_evid(_COMBOS[0]['n']), aufwand='mittel', wirk=_COMBOS[0]['med'] / POST_MED if POST_MED else 1,
        kurz='Gewinner-Kombis als Vorlagen', big=_fx(_COMBOS[0]['med']), bigsub=f"{esc(_COMBOS[0]['thema'])} als {esc(_COMBOS[0]['fmt'])}", akt='Fertige Vorlagen an alle Märkte geben.',
        wirkung=_rel(_COMBOS[0]['med'])[1], wcls=_rel(_COMBOS[0]['med'])[0],
        bars=[(f'{esc(c["thema"])} als {esc(c["fmt"])}', _rel(c['med'])[1], c['med'], _rel(c['med'])[0] == 'gut') for c in _COMBOS]))
if _HR_BEST and _HR_VOLL:
    _HEBEL.append(_hebel(4,
        f"Später posten: {' oder '.join(str(r['h']) + ' Uhr' for r in _HR_BEST)} statt {_HR_VOLL['h']} Uhr",
        f"Um <b>{_HR_VOLL['h']} Uhr</b> posten die meisten ({de(_HR_VOLL['n'])} Beiträge) – der Feed ist voll, Posts laufen <b>{_rel(_HR_VOLL['med'])[1]}</b>. "
        f"Um <b>{_HR_BEST[0]['h']} Uhr</b> laufen sie <b>{_rel(_HR_BEST[0]['med'])[1]}</b>."
        + (f" Stärkster Tag: <b>{esc(_WD_BEST['label'])}</b>, schwächster: {esc(_WD_WORST['label'])}." if _WD_BEST and _WD_WORST else ''),
        'Beiträge vorplanen und abends veröffentlichen. Den Montag eher meiden.',
        'Für alle Märkte', ['Frequenz'],
        bedeutung='Abends ist weniger Konkurrenz im Feed: gleicher Aufwand, mehr Reaktion. Die Uhrzeit allein erklärt den Unterschied aber nicht vollständig.', beispiel=_beispiel(lambda q: _hour(q) == _HR_BEST[0]['h'], f"gepostet um {_HR_BEST[0]['h']} Uhr"), messung=f"Anteil der Posts nach 19 Uhr und deren Reaktionen pro 100 Follower im Vergleich zu {_HR_VOLL['h']} Uhr.", evid=_evid(min(_HR_BEST[0]['n'], _HR_VOLL['n'])), aufwand='gering', wirk=_HR_BEST[0]['med'] / POST_MED if POST_MED else 1,
        kurz=f"Um {_HR_BEST[0]['h']} Uhr posten, nicht um {_HR_VOLL['h']}", big=_fx(_HR_BEST[0]['med']), bigsub=f"{_HR_BEST[0]['h']} Uhr vs. normaler Post", akt='Vorplanen und abends veröffentlichen.',
        wirkung=f'{_mal(_HR_BEST[0]["med"], _HR_VOLL["med"])} Unterschied', wcls=_rel(_HR_BEST[0]['med'])[0],
        bars=[(f'{_HR_BEST[0]["h"]} Uhr', _rel(_HR_BEST[0]['med'])[1], _HR_BEST[0]['med'], _rel(_HR_BEST[0]['med'])[0] == 'gut'),
              (f'{_HR_VOLL["h"]} Uhr', _rel(_HR_VOLL['med'])[1], _HR_VOLL['med'], _rel(_HR_VOLL['med'])[0] == 'gut')]))
if _DCO_TOP:
    _k = _KONK[_DCO_TOP]
    _rec = _KONK[_REC_TOP] if _REC_TOP else None
    _HEBEL.append(_hebel(5,
        'Angebote in Anzeigen, Team-Content ins Recruiting',
        f"{BRAND_DE[_DCO_TOP]} schaltet <b>{_k['dco']} Anzeigen, die Angebote automatisch aus dem Sortiment zeigen</b> – EDEKA {_ED['dco']}. "
        + (f"{BRAND_DE[_REC_TOP]} wirbt in {_rec['recruiting']} von {_rec['n']} Anzeigen um Personal – EDEKA in {_ED['recruiting']}." if _rec and _rec['recruiting'] else ''),
        'Preise gehören in dynamische Anzeigen, nicht in den organischen Feed. Team &amp; Azubis laufen organisch schon am besten – auch als Recruiting-Anzeige nutzen.',
        'Für die Zentrale / Media', ['Umsatz', 'Preiswahrnehmung'], 6,
        bedeutung='Der Wettbewerb nutzt Anzeigen für Preise und Personal, EDEKA lässt diese Fläche weitgehend frei. Wie gut die Anzeigen wirken, lässt sich ohne Zugang zum Meta-Werbekonto nicht messen.', beispiel='', messung='Zahl der dynamischen Angebots-Anzeigen in der Meta-Werbebibliothek. Kosten und Umsatz nur mit Zugang zum Ads Manager.', evid=_evid(None, 'einmalige Abfrage der Meta-Werbebibliothek, max. 20 Anzeigen je Marke'), aufwand='hoch', wirk=(_k['dco'] / _ED['dco']) if _ED['dco'] else 3,
        kurz='Angebote in Anzeigen', big=f"{_ED['dco']} : {_k['dco']}", bigsub=f"Angebots-Anzeigen EDEKA : {BRAND_DE[_DCO_TOP]}", akt='Preise in dynamische Anzeigen statt in den Feed.',
        wirkung=f'DCO-Anzeigen {_k["dco"]} vs {_ED["dco"]}', wcls='info',
        bars=[(f'{BRAND_DE[_DCO_TOP]}', str(_k['dco']), _k['dco'], False),
              ('EDEKA', str(_ED['dco']), _ED['dco'], True)]) )

_HEBEL.sort(key=lambda t: -t[0])
_PRIOS = '<div class="span6 hgrid">' + ''.join(h(i + 1) for i, (_, h) in enumerate(_HEBEL)) + '</div>'

def _thema_tab():
    mx = max([r['med'] for r in THEMEN_ROWS if r['n'] >= 20] or [1])
    ges = max(1, sum(x['n'] for x in THEMEN_ROWS if x['n'] >= 20))
    pos = min(100, POST_MED / mx * 100)
    rows = []
    for r in THEMEN_ROWS:
        if r['n'] < 20:
            continue
        cls, lab = _empf(r)
        w = max(3, r['med'] / mx * 100)
        rows.append(f"""<tr><td class="strong">{esc(r['thema'])}</td>
          <td class="num">{_bruch(r['n'] / ges)}</td>
          <td><div class="tbar"><div class="tfill {cls}" style="width:{w:.0f}%"></div><div class="tnorm" style="left:{pos:.0f}%"></div></div></td>
          <td class="strong">{_rel(r['med'])[1]}</td>
          <td><span class="badge {cls}">{lab}</span></td></tr>""")
    return ('<div class="tw"><table class="themtab"><thead><tr><th>Thema</th><th class="num">So oft gepostet</th>'
            '<th>Wie gut kommt es an?</th><th>Im Vergleich zu normal</th><th>Empfehlung</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')

# Beispiel-Woche (ohne interne Daten)
_WOCHE = ''
if _COMBOS and WD_ORD and _HR_BEST:
    _tage = sorted(WD_ORD[:3], key=lambda r: WD_DE.index(r['label']))
    _slots = []
    for i, t in enumerate(_tage):
        c = _COMBOS[i % len(_COMBOS)]
        h = _HR_BEST[i % len(_HR_BEST)]['h']
        _slots.append(f'<div class="wrow"><span class="wtag">{esc(t["label"])}</span><span class="wzeit">{h}:00 Uhr</span>'
                      f'<span class="wwas">{esc(c["thema"])}<em>als {esc(c["fmt"])}</em></span></div>')
    if _FMT_BONUS:
        _slots.append(f'<div class="wrow"><span class="wtag">Bonus</span><span class="wzeit">1× pro Woche</span>'
                      f'<span class="wwas">Humor/Team<em>als {esc(_FMT_BONUS["label"])}</em></span></div>')
    _WOCHE = '<div class="woche">' + ''.join(_slots) + '</div>'

# ---- Kennzahlen mit Urteil: lokale Märkte vs. Hauptkonto ----
import csv as _csv
_TIPO = {r['handle']: r['tipo'] for r in _csv.DictReader(open(os.path.join(DATA, 'accounts.csv')))}
def _er_list(pred):
    return [((q.get('likes') or 0) + (q.get('comments') or 0)) / q['followers'] * 100
            for q in posts if q.get('likes_ok') and q['followers'] and pred(q)]
_LOK = _er_list(lambda q: _TIPO.get(q['handle']) in ('mercado', 'sin confirmar'))
LOK_MED = statistics.median(_LOK) if _LOK else 0
_HAUPT = [q for q in posts if q['handle'] == 'edeka' and q.get('likes_ok') and q['followers']]
HAUPT_MED = statistics.median([((q.get('likes') or 0) + (q.get('comments') or 0)) / q['followers'] * 100 for q in _HAUPT]) if _HAUPT else None
HAUPT_INT = statistics.median([(q.get('likes') or 0) + (q.get('comments') or 0) for q in _HAUPT]) if _HAUPT else None
HAUPT_F = _HAUPT[0]['followers'] if _HAUPT else 0
_SCHWACH_ANT = sum(r['n'] for r in _SCHWACH) / max(1, sum(r['n'] for r in THEMEN_ROWS))

def _urteil_bench(v):
    if v >= BENCH_ER * 1.5:
        return ('gut', 'Gut')
    if v >= BENCH_ER * 0.8:
        return ('mittel', 'Im Schnitt')
    return ('schwach', 'Schwach')

def _kbar(label, wert, anteil, gut=True):
    return (f'<div class="kb"><span class="kbl">{label}</span><div class="kbt"><div class="kbf {"g" if gut else "s"}" '
            f'style="width:{max(2, min(100, anteil * 100)):.0f}%"></div></div><span class="kbw">{wert}</span></div>')

def _kpi(titel, cls, urteil, zahl, einheit, bars, satz):
    return f"""<div class="vk"><div class="vkh"><span class="vkt">{titel}</span><span class="vku u-{cls}">{urteil}</span></div>
      <div class="vkz"><b>{zahl}</b><span>{einheit}</span></div>
      <div class="kbs">{''.join(bars)}</div>
      </div>"""

_KPIS = []
_c, _u = _urteil_bench(LOK_MED)
_mx = max(LOK_MED, BENCH_ER) or 1
_KPIS.append(_kpi('Lokale Märkte', _c, _u, _z(LOK_MED), 'von 100 Followern reagieren',
    [_kbar('Märkte', _z(LOK_MED), LOK_MED / _mx, LOK_MED >= BENCH_ER), _kbar('Branche', _z(BENCH_ER, 2), BENCH_ER / _mx, False)],
    'auf einen normalen Beitrag mit Like oder Kommentar.'))
if HAUPT_MED is not None:
    _c, _u = _urteil_bench(HAUPT_MED)
    _mx = max(HAUPT_MED, BENCH_ER) or 1
    _KPIS.append(_kpi('Hauptkonto @edeka', _c, _u, _z(HAUPT_MED, 2), f'von 100 Followern reagieren · {de(HAUPT_F)} Follower',
        [_kbar('@edeka', _z(HAUPT_MED, 2), HAUPT_MED / _mx, HAUPT_MED >= BENCH_ER), _kbar('Branche', _z(BENCH_ER, 2), BENCH_ER / _mx, False)],
        f'{de(HAUPT_F)} Follower, aber nur rund {de(HAUPT_INT)} Reaktionen pro Beitrag.'))
_KPIS.append(_kpi('Themen-Mix', 'schwach' if _SCHWACH_ANT >= 0.4 else 'mittel', 'Ausbaufähig' if _SCHWACH_ANT < 0.4 else 'Schwach',
    _bruch(_SCHWACH_ANT), 'Posts laufen unter normal',
    [_kbar('Gut', f'{(1 - _SCHWACH_ANT) * 100:.0f} %', 1 - _SCHWACH_ANT, True), _kbar('Schwach', f'{_SCHWACH_ANT * 100:.0f} %', _SCHWACH_ANT, False)],
    ('Vor allem ' + ' und '.join(esc(r['thema']) for r in _SCHWACH[-2:]) + '.') if _SCHWACH else ''))
_akt = N_AKTIV30 / max(1, N_KONTEN)
_KPIS.append(_kpi('Aktivität', 'gut' if _akt >= 0.8 else 'mittel', 'Gut' if _akt >= 0.8 else 'Ausbaufähig',
    f'{N_AKTIV30}/{de(N_KONTEN)}', 'Profile aktiv',
    [_kbar('Aktiv', f'{_akt * 100:.0f} %', _akt, True), _kbar('Still', de(N_KONTEN - N_AKTIV30), 1 - _akt, False)],
    'mindestens ein Beitrag in den letzten 30 Tagen.'))
KPI_HTML = '<div class="vkgrid">' + ''.join(_KPIS) + '</div>'

# ---- Berlin im Blick ----
try:
    _REG = json.load(open(os.path.join(DATA, 'regionen.json')))
except Exception:
    _REG = {}
BERLIN_SET = set(_REG.get('berlin') or [])
BERLIN_HTML = ''
if BERLIN_SET:
    def _reg_stats(pred):
        prof = [a for a in accounts if pred(a['handle'])]
        er = _er_list(lambda q: pred(q['handle']))
        akt = [a for a in prof if any(q['handle'] == a['handle'] and in_days(q, 0, 30) for q in posts)]
        n30 = len([q for q in posts if pred(q['handle']) and in_days(q, 0, 30)])
        return {'n': len(prof), 'aktiv': len(akt), 'med': statistics.median(er) if er else 0,
                'pw': (n30 / max(1, len(akt))) / 30 * 7}
    _B = _reg_stats(lambda h: h in BERLIN_SET)
    _R = _reg_stats(lambda h: h not in BERLIN_SET and _TIPO.get(h) in ('mercado', 'sin confirmar'))
    _bc, _bt = _rel(_B['med'], _R['med'] or None)
    BERLIN_HTML = f"""
        <div class="card span6">
          <h3>Berlin im Blick</h3>
          <p class="hint">Berliner Profile im Vergleich zu allen anderen Märkten. {esc(_REG.get('_hinweis', ''))}</p>
          <div class="berl">
            <div class="bz"><span class="bl">Erfasste Berliner Profile</span><b>{_B['n']}</b><span class="bs">{_B['aktiv']} davon aktiv in 30 Tagen</span></div>
            <div class="bz"><span class="bl">Reaktionen pro 100 Follower</span><b>{_z(_B['med'])}</b><span class="bs">andere Märkte: {_z(_R['med'])} → Berlin <span class="pill {_bc if _bc != 'info' else 'mittel'}">{_bt}</span></span></div>
            <div class="bz"><span class="bl">Posts pro Woche je aktivem Profil</span><b>{_z(_B['pw'])}</b><span class="bs">andere Märkte: {_z(_R['pw'])}</span></div>
          </div>
        </div>"""

# ---- Interne Ebene: nur wenn data/intern/ vorhanden (nie im öffentlichen Repo) ----
def _intern(name):
    pfad = os.path.join(DATA, 'intern', name)
    try:
        return json.load(open(pfad))
    except Exception:
        return None
JAHRESSTART = _intern('jahresstart.json')
KAMPAGNEN = _intern('kampagnen.json')

PLAN_JS_HTML = ''
if JAHRESSTART:
    _jr = JAHRESSTART.get('jahr', 2027)
    _rows = []
    for w in JAHRESSTART.get('wochen', []):
        try:
            _von = dt.date.fromisocalendar(_jr, w['kw'], 1).strftime('%d.%m.')
            _bis = dt.date.fromisocalendar(_jr, w['kw'], 7).strftime('%d.%m.')
        except Exception:
            _von = _bis = ''
        _th = next((r for r in THEMEN_ROWS if r['thema'] == w.get('thema')), None)
        _cmb = next((c for c in _COMBOS if c['thema'] == w.get('thema') and c['fmt'] == w.get('format')), None)
        _wert = _rel(_cmb['med'])[1] if _cmb else (_rel(_th['med'])[1] if _th else '')
        _zeit = f"{_HR_BEST[0]['h']}:00 Uhr" if _HR_BEST else ''
        _rows.append(f"""<div class="kw">
          <div class="kwh"><b>KW {w['kw']}</b><span>{_von}–{_bis}</span></div>
          <div class="kwa">{esc(w.get('aktion', ''))}</div>
          <div class="kwf">{esc(w.get('fokus', ''))}{(' · ' + esc(w['anlass'])) if w.get('anlass') else ''}</div>
          <div class="kwi"><span class="hlbl">Social-Idee</span>{esc(w.get('idee', ''))}
            <div class="kwm"><span class="pill info">{esc(w.get('format', ''))} · {_zeit}</span>{(f'<span class="pill gut">{esc(w.get("thema"))}: {_wert}</span>') if _wert else ''}</div></div>
        </div>""")
    PLAN_JS_HTML = f"""
        <div class="card span6 intern">
          
          <h3>Jahresstart {_jr}: der Social-Plan für KW 1 bis 8</h3>
          <p class="hint">Oben die geplanten Aktionen, unten unser Vorschlag für Social – jeweils mit dem Format und der Uhrzeit, die laut Daten am besten laufen. Botschaft: „{esc(JAHRESSTART.get('botschaft', ''))}“</p>
          <div class="kwgrid">{''.join(_rows)}</div>
        </div>"""

KAMP_HTML = ''
if KAMPAGNEN:
    _cards = []
    for k in KAMPAGNEN.get('kampagnen', []):
        _w = ''.join(f'<div class="kz"><b>{esc(x["zahl"])}</b><span>{esc(x["text"])}</span></div>' for x in k.get('werte', []))
        _cards.append(f"""<div class="card span3 kamp">
          <div class="kmeta">{esc(k.get('zeit', ''))} · {esc(k.get('wo', ''))}</div>
          <h3>{esc(k['name'])}</h3>
          <div class="kwerte">{_w}</div>
          {('<div class="kbez">' + esc(k['bezug']) + '</div>') if k.get('bezug') else ''}
          {_ziele(k.get('ziel', []))}
          <div class="hwer">{esc(k.get('stand', ''))}</div>
        </div>""")
    KAMP_HTML = f"""
        <div class="card blue span6">
          
          <h3>06 · Kampagnen – was Social schon bewirkt hat</h3>
          <p class="kurz">{esc(KAMPAGNEN.get('muster', ''))}</p>
        </div>
        {''.join(_cards)}
        <div class="card span6"><p class="hint" style="margin:0">Quelle: interne Unterlagen EDEKA Minden-Hannover. Für Reichweite und Kosten je Kampagne braucht es weiterhin den Zugang zum Meta Ads Manager.</p></div>"""

_KURZ = ''
if _TH_BEST and _TH_WORST and _FMT_BASE and _HR_BEST:
    _KURZ = (f"<b>{esc(_TH_BEST[0]['thema'])}</b> läuft {_mal(_TH_BEST[0]['med'], _TH_WORST['med'])} so gut wie <b>{esc(_TH_WORST['thema'])}</b> – "
             f"trotzdem ist {_bruch(_SCHWACH_ANT)} Posts ein Thema, das schlechter läuft als normal. "
             f"Größter Hebel: Preise mit Menschen erzählen, als <b>{esc(_FMT_BASE['label'])}</b> posten, abends um <b>{_HR_BEST[0]['h']} Uhr</b>.")
HEADLINE = ('Preis beweisen – mit Menschen, nicht mit Preisschildern.'
            if _TH_WORST and 'Angebot' in _TH_WORST['thema'] else 'Was jetzt tun – die Kurzfassung')

# ---- Hypothese prüfen ----
_HYP = ''
if _TH_BEST and _TH_WORST:
    _hb, _hw = _TH_BEST[0], _TH_WORST
    _HYP = f"""
        <details class="card span6 hyp">
          <summary><span class="eyebrow2">Strategische Hypothese</span><span class="ev ev-mittel">Teilweise gestützt</span>
            <span class="hypt">„{HEADLINE}“</span><span class="hyps">Menschen-Posts {_rel(_hb['med'])[1]}, reine Preis-Posts {_rel(_hw['med'])[1]}. Die Kombination ist noch nicht getestet.</span><span class="chev"></span></summary>
          <div class="hypg">
            <div class="hypc ok"><b>Das zeigen die Daten</b><span>Posts mit Menschen und Humor laufen {_rel(_hb['med'])[1]}, reine Preis-Posts {_rel(_hw['med'])[1]} als ein normaler Beitrag ({de(_hb['n'])} und {de(_hw['n'])} Beiträge).</span></div>
            <div class="hypc open"><b>Noch offen</b><span>Ob Preis und Menschen <i>zusammen</i> besser laufen, ist nicht gemessen. Jeder Post hat nur ein Thema.</span></div>
            <div class="hypc next"><b>Nächster Schritt</b><span>4 Wochen testen: Preis-Posts mit Gesicht gegen reine Preis-Posts.</span></div>
          </div>
        </details>"""

# ---- Was die viralen Posts gemeinsam haben ----
_MUSTER = ''
_MUSTER_SUM = ''
_TH_URL = {q.get('url'): q.get('thema') for q in posts}
for _q in ueberflieger:
    _q['thema'] = _TH_URL.get(_q.get('url'), _q.get('thema'))
if ueberflieger:
    _vp = [q for q in posts if q.get('likes_ok')]
    _nv = len(ueberflieger); _na = max(1, len(_vp))
    _fmt_top, _fmt_n = FL_FMT.most_common(1)[0]
    _fmt_key = {v: k for k, v in _FMT_MAP.items()}.get(_fmt_top)
    _fmt_all = sum(1 for q in _vp if q.get('kind') == _fmt_key) / _na
    _th_v = collections.Counter(q.get('thema') for q in ueberflieger if q.get('thema') not in (None, 'nicht zugeordnet', 'Sonstiges'))
    _abend_v = sum(1 for q in ueberflieger if (_hour(q) or 0) >= 19) / _nv
    _abend_a = sum(1 for q in _vp if (_hour(q) or 0) >= 19) / _na
    _rows = [(f'{_fmt_top}', f'{_fmt_n} von {_nv}', f'{_fmt_all * 100:.0f} % aller Posts')]
    if _th_v:
        _t, _c = _th_v.most_common(1)[0]
        _ta = sum(1 for q in _vp if q.get('thema') == _t) / _na
        _rows.append((esc(_t), f'{_c} von {_nv}', f'{_ta * 100:.0f} % aller Posts'))
    _rows.append(('Gepostet ab 19 Uhr', f'{round(_abend_v * _nv)} von {_nv}', f'{_abend_a * 100:.0f} % aller Posts'))
    _bsp = ''.join(f'<a class="hbsp" href="{esc(q.get("url") or "#")}" target="_blank" rel="noopener"><b>@{esc(q["handle"])}</b> · {FMT_DE.get(q.get("kind"), "")} <br>{de((q.get("likes") or 0) + (q.get("comments") or 0))} Reaktionen statt sonst rund {de((_acc_idx.get(q["handle"]) or {}).get("med_inter"))} <span>ansehen →</span></a>' for q in ueberflieger[:3])
    _MUSTER_SUM = ' · '.join(f'{v} {l}' for l, v, a in _rows[:2])
    _MUSTER = f"""
        <div class="card span6">
          <h3>Was die {_nv} viralen Posts gemeinsam haben</h3>
          <div class="mgrid">{''.join(f'<div class="mz"><span class="ml">{l}</span><b>{v}</b><span class="mv">vs. {a}</span></div>' for l, v, a in _rows)}</div>
          <p class="hint" style="margin-top:14px">Zum Nachmachen: die drei stärksten Beispiele</p>
          <div class="mbsp">{_bsp}</div>
          <p class="hint" style="margin-top:10px">Viral = mindestens 3× so viele Reaktionen wie sonst beim selben Profil. Bei {_nv} Posts: Muster, keine Gesetze.</p>
        </div>"""

EXPLORER_EXTRA = f"""
        <div class="card span6">
          <h3>Welche Themen funktionieren – und welche nicht</h3>
          <p class="hint">Die gestrichelte Linie ist ein normaler Beitrag. Balken rechts davon = besser, links davon = schlechter. Ab 20 Beiträgen je Thema.</p>
          {_thema_tab()}
        </div>
        {BERLIN_HTML}
        <div class="card span6">
          <h3>So liest du die Zahlen</h3>
          <ul class="bul glossar">
            <li><b>„von 100 Followern“</b> – so viele liken oder kommentieren einen Beitrag. Fachbegriff: Engagement-Rate.</li>
            <li><b>Normaler Beitrag</b> – der mittlere Wert aller {de(N_POSTS_GUELTIG)} Posts: {_z(POST_MED)} von 100.</li>
            <li><b>Evidenz</b> – stark: mindestens 100 Beiträge je verglichener Gruppe, mittel: mindestens 30, sonst begrenzt.</li>
            <li><b>Zusammenhang ≠ Ursache</b> – die Daten zeigen, was zusammen auftritt, nicht was es verursacht.</li>
          </ul>
        </div>"""

def _sektion(nr, titel, inhalt, zusammenfassung='', offen=True):
    return f"""<details class="acc span6"{' open' if offen else ''}>
          <summary class="frage"><span class="fnr">{nr}</span><span class="ftx"><span class="fti">{titel}</span>{f'<span class="fsu">{zusammenfassung}</span>' if zusammenfassung else ''}</span><span class="chev"></span></summary>
          <div class="grid accg">{inhalt}</div>
        </details>"""

# ---------------- Pausche 04 · Trends & Stimmen --------------------------
def _lade_json(fn):
    try:
        with open(os.path.join(DATA, fn), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def _dtagen(s):
    """'2026-11-26' -> '26.11.2026'"""
    s = str(s or '').strip()[:10]
    try:
        return dt.datetime.strptime(s, '%Y-%m-%d').strftime('%d.%m.%Y')
    except ValueError:
        return str(s or '–')

TRENDS = _lade_json('trends.json')      # scripts/scrape_trends.py (montags)
KOMS = _lade_json('comments.json')      # scripts/scrape_comments.py (montags)

def _dts(s):
    """'2026-11-26 12:08' -> '26.11.2026, 12:08'"""
    s = str(s or '').strip()
    if not s:
        return '–'
    d, _, h = s.partition(' ')
    out = _dtagen(d)
    return out + (', ' + h[:5] if h else '')

TS_TAB = ('<span class="tab2" data-s="s6" onclick="sec(\'s6\',this)">'
          '04 Trends &amp; Stimmen<small class="tabd">'
          'Was gerade läuft &amp; was Kunden sagen</small></span>')

# -- 1-Zeiler je Block für die Übersicht (s0) --
_ts_sum = []
if TRENDS.get('formate') and TRENDS.get('n_relevant'):
    _bf = max(TRENDS['formate'].items(), key=lambda kv: (kv[1] or {}).get('engagement') or 0)
    _ts_sum.append(
        '<div class="catrow"><div class="c1">Trends: <b>%s</b> liefert Ø %s Interaktionen'
        ' je Reel — %s von %s geprüften Reels sind relevant für EDEKA</div>'
        '<div class="c2">%s</div></div><div class="catbar"><div style="width:100%%"></div></div>'
        % (esc(_bf[0]), de(_bf[1].get('engagement') or 0),
           de(TRENDS.get('n_relevant') or 0), de(TRENDS.get('n_gesamt') or 0),
           _dtagen(TRENDS.get('stand'))))
if KOMS.get('posts') and KOMS.get('n_kommentare'):
    _off = int(KOMS.get('offene_fragen') or 0)
    _ts_sum.append(
        '<div class="catrow"><div class="c1">Stimmen: <b>%s %%</b> der %s Kommentare '
        'sind positiv — <b>%s</b> offene Fragen%s</div><div class="c2">%s</div></div>'
        '<div class="catbar"><div style="width:%s%%"></div></div>'
        % (int((KOMS.get('ton') or {}).get('positiv') or 0), de(KOMS['n_kommentare']),
           de(_off), ' — sollte EDEKA beantworten' if _off else ' — alles beantwortet',
           esc(_dts(KOMS.get('stand'))),
           int((KOMS.get('ton') or {}).get('positiv') or 0)))
TS_SUM = (('<div class="card span6"><span class="arrow">↗</span>'
           '<h3>Was gerade läuft &amp; was Kunden sagen</h3>'
           + ''.join(_ts_sum) + '</div>') if _ts_sum else '')

# -- Die Pausche selbst --
_ts_teile = []
_bestfmt = None
if TRENDS.get('formate'):
    _bestfmt = max(TRENDS['formate'].items(), key=lambda kv: (kv[1] or {}).get('engagement') or 0)
_kl, _stands = [], []
if _bestfmt:
    _kl.append('%s läuft gerade am besten — Ø %s Interaktionen je Reel'
               % (_bestfmt[0], de((_bestfmt[1] or {}).get('engagement') or 0)))
if KOMS.get('ton'):
    _kl.append('%s %% der Kommentare positiv, %s offene Fragen'
               % (int(KOMS['ton'].get('positiv') or 0), de(KOMS.get('offene_fragen') or 0)))
if TRENDS.get('stand'):
    _stands.append('Trends ' + _dtagen(TRENDS['stand']))
if KOMS.get('stand'):
    _stands.append('Kommentare ' + esc(_dts(KOMS['stand'])))
_ts_hint = (('Datenstand: ' + ' · '.join(_stands) + ' · neue Auswertung jeden Montag, 05:00 UTC')
            if _stands else 'Noch keine Daten — der erste Lauf startet montags um 05:00 UTC.')
_ts_teile.append(
    '<div class="card blue span6">'
    '<span class="arrow">↗</span><h3>04 · Trends &amp; Stimmen</h3>'
    '<p class="hint">%s</p><p class="hint" style="font-weight:600">%s</p>'
    '</div>'
    % (esc(' · '.join(_kl)) if _kl
       else 'Was gerade in der Nische läuft und was Kunden zu EDEKA sagen', _ts_hint))

# --- Block A: Trends in der Nische ---
if TRENDS.get('top'):
    fm = TRENDS.get('formate') or {}
    maxe = max([(v or {}).get('engagement') or 0 for v in fm.values()] + [1])
    barr = ''
    for name, v in sorted(fm.items(), key=lambda kv: -((kv[1] or {}).get('engagement') or 0)):
        e = (v or {}).get('engagement') or 0
        barr += ('<div class="catrow"><div class="c1">%s · %s Reels</div><div class="c2">Ø %s</div></div>'
                 '<div class="catbar"><div style="width:%d%%;background:#2A60FF"></div></div>'
                 % (esc(name), de((v or {}).get('anzahl') or 0), de(e),
                    max(4, round(e * 100 / maxe))))
    _ts_teile.append(
        '<div class="card span6"><span class="arrow">↗</span>'
        '<h3>Trends in der Nische</h3>'
        '<p class="hint">Was auf Instagram gerade läuft und für EDEKA brauchbar ist. '
        '%s von %s geprüften Reels sind relevant. Zahlen = Ø Interaktionen (Likes + '
        'Kommentare) je Reel — höher ist besser.</p>%s</div>'
        % (de(TRENDS.get('n_relevant') or 0), de(TRENDS.get('n_gesamt') or 0), barr))

    zellen = ''
    for i, t in enumerate(TRENDS['top'][:12]):
        img = ''
        if t.get('thumbnail'):
            try:
                img = dl(t['thumbnail'], 't%02d.jpg' % i)
            except Exception:
                img = ''
        bild = ('<img loading="lazy" src="%s" alt="">' % esc(img)) if img else '<div class="ph">IG</div>'
        zahl = ('%s Aufrufe' % de(t['views'])) if t.get('views') else '%s Likes' % de(t.get('likes') or 0)
        direkt = t.get('transfer') == 'direkt'
        pill = 'gut' if direkt else 'schwach'
        plabel = 'direkt übertragbar' if direkt else 'mit Anpassung'
        datum = (' · ' + _dtagen(t['datum'])) if t.get('datum') else ''
        zellen += ('<a class="tsc" href="%s" target="_blank" rel="noopener">%s'
                   '<div class="tcb"><div class="tcc">@%s</div>'
                   '<div class="tcm">%s · %s%s</div>'
                   '<span class="pill %s">%s</span></div></a>'
                   % (esc(t['url']), bild, esc(t['creator']), zahl,
                      esc(t['format']), datum, pill, plabel))

    testen = []
    for t in TRENDS['top'][:3]:
        wer = ('direkt übertragbar' if t.get('transfer') == 'direkt'
               else 'mit Anpassung übertragbar')
        testen.append('<li><b>@%s</b>: %s (%s Aufrufe) — %s</li>'
                      % (esc(t['creator']), esc(t['format']),
                         de(t['views'] or t.get('likes') or 0), wer))
    if _bestfmt:
        testen.append('<li><b>%s</b> ansehen: Ø %s Interaktionen je Reel — '
                      'das stärkste Format im aktuellen Lauf</li>'
                      % (_bestfmt[0], de((_bestfmt[1] or {}).get('engagement') or 0)))

    _ts_teile.append(
        '<div class="card span6"><span class="arrow">↗</span>'
        '<h3>Reels zum Nachmachen</h3>'
        '<p class="hint">Die stärksten Treffer der letzten Suche. Klick öffnet den Reel '
        'auf Instagram. Die Blaue Markierung heißt: so könnt ihr es direkt nachbauen.</p>'
        '<div class="tsgrid">%s</div>'
        '<div class="tsintern">'
        '<h3 style="font-size:20px">Das sollte EDEKA testen</h3><ul class="bul">%s</ul></div>'
        '</div>' % (zellen, ''.join(testen)))

    _ts_teile.append(
        '<div class="card span3"><span class="arrow">↗</span><h3>Methodik</h3>'
        '<p class="hint">So entsteht diese Auswertung:</p>'
        '<ul class="bul">'
        '<li>Quellen: Instagram-Suche &amp; Hashtags (treg), wöchentlich montags.</li>'
        '<li>Eigene EDEKA-Konten und ausgeschlossene Konten sind entfernt.</li>'
        '<li>Jev prüft jedes Reel: relevant für einen deutschen Supermarkt? '
        'Format übertragbar?</li>'
        '<li>Behalten: Relevanz ≥ 0,7 und „direkt“ oder „mit Anpassung“.</li>'
        '<li>Ein Lauf kostet etwa %s $.</li></ul>'
        '<details class="tsdet"><summary>Alle Quote-Quellen einblenden</summary>'
        '<ul class="bul">%s</ul></details></div>'
        % (de(round(TRENDS.get('kosten_usd') or 0, 2) or 0.04, 2),
           ''.join('<li>%s</li>' % esc(q) for q in (TRENDS.get('queries') or []))))
else:
    _ts_teile.append(
        '<div class="card span6"><span class="arrow">↗</span><h3>Trends in der Nische</h3>'
        '<p class="hint">Noch keine Daten — die nächste Analyse läuft montags um 05:00 UTC '
        'und füllt diesen Abschnitt automatisch.</p></div>')

# --- Block B: Stimmen (Kommentare) ---
if KOMS.get('posts'):
    ton = KOMS.get('ton') or {}
    pos = int(ton.get('positiv') or 0)
    neu = int(ton.get('neutral') or 0)
    neg = int(ton.get('negativ') or 0)
    off = int(KOMS.get('offene_fragen') or 0)

    med = ('<div class="tsmom"><i class="p" style="width:%d%%"></i>'
           '<i class="n" style="width:%d%%"></i><i class="x" style="width:%d%%"></i></div>'
           '<div class="tonlbl"><span><span class="dotp"></span>positiv <b>%d %%</b></span>'
           '<span><span class="dotn"></span>neutral <b>%d %%</b></span>'
           '<span><span class="dotx"></span>negativ <b>%d %%</b></span></div>'
           % (pos, neu, neg, pos, neu, neg))

    kpis = ('<div class="tsk">'
            '<div class="tskb"><div class="l">Kommentare geprüft</div><div class="k">%s</div>'
            '<div class="s">%s Beiträge der letzten 14 Tage</div></div>'
            '<div class="tskb"><div class="l">Stimmung</div><div class="k">%d %%</div>'
            '<div class="s">%d %% negativ — das ist der Anteil, der EDEKA fordert</div></div>'
            '<div class="tskb %s"><div class="l">Offene Fragen</div><div class="k">%s</div>'
            '<div class="s">%s</div></div></div>'
            % (de(KOMS.get('n_kommentare') or 0), de(KOMS.get('n_posts') or 0), pos, neg,
               'schlecht' if off else 'gut', de(off),
               'wartet auf eine Antwort — sollte EDEKA reagieren' if off
               else 'gut — jede Frage wurde beantwortet'))

    themen = (KOMS.get('themen') or [])[:6]
    maxt = max([(t.get('anzahl') or 0) for t in themen] + [1])
    themen_html = ''
    for t in themen:
        a = t.get('anzahl') or 0
        themen_html += ('<div class="catrow"><div class="c1">%s</div><div class="c2">%s</div></div>'
                        '<div class="catbar"><div style="width:%d%%;background:#2A60FF"></div></div>'
                        % (esc(t.get('thema') or ''), de(a), max(4, round(a * 100 / maxt))))

    BEI_ART = {'positiv': 'gut', 'neutral': 'mittel', 'negativ': 'schwach'}
    bei_html = ''
    for b in (KOMS.get('beispiele') or [])[:4]:
        bei_html += ('<div class="kb"><div class="kbm">%s · %s</div>%s</div>'
                     % (esc(str(b.get('ton') or '')), esc(str(b.get('thema') or '')),
                        esc(str(b.get('text') or ''))))

    akt_html = ''.join('<li>%s</li>' % esc(str(a)) for a in (KOMS.get('aktionen') or [])[:3])

    zeilen = ''
    for p in sorted(KOMS.get('posts') or [], key=lambda x: -(x.get('n') or 0))[:12]:
        zeilen += ('<tr><td><a href="%s" target="_blank" rel="noopener">@%s</a></td>'
                   '<td class="num">%s</td><td class="num">%d %%</td><td class="num">%d %%</td></tr>'
                   % (esc(p['url']), esc(p.get('profil') or ''), de(p.get('n') or 0),
                      int(p.get('anteil_positiv') or 0), int(p.get('anteil_negativ') or 0)))

    _ts_teile.append(
        '<div class="card span6"><span class="arrow">↗</span>'
        '<h3>Was Kunden sagen</h3>'
        '<p class="hint">Kommentare zu den %s aktivsten EDEKA-Beiträgen der letzten '
        '14 Tage. Ton und Thema bewertet mit Jev, Nutzernamen sind nicht gespeichert.</p>%s%s%s'
        '<details class="tsdet"><summary>Kommentare je Beitrag — Tabelle einblenden</summary>'
        '<table class="tstbl"><thead><tr><th>Beitrag</th><th class="num">Kommentare</th>'
        '<th class="num">positiv</th><th class="num">negativ</th></tr></thead>'
        '<tbody>%s</tbody></table></details></div>'
        % (de(KOMS.get('n_posts') or 0), med, kpis, themen_html, zeilen))

    _ts_teile.append(
        '<div class="card span3"><span class="arrow">↗</span><h3>Stimmen im Detail</h3>'
        '<p class="hint">Die häufigsten Themen — worüber gesprochen wird:</p>%s'
        '<p class="hint" style="margin-top:6px">Kommentare ohne Namen, '
        'Stichprobe aus dem Lauf:</p>%s</div>' % (themen_html, bei_html))

    _ts_teile.append(
        '<div class="card span3"><span class="arrow">↗</span><h3>Fazit</h3>'
        '<p class="hint">%s</p>'
        '<p class="hint" style="font-weight:600;color:#16150F">Das sollte EDEKA tun:</p>'
        '<ul class="bul tsakt">%s</ul></div>'
        % (esc(str(KOMS.get('fazit') or '')), akt_html))
else:
    _ts_teile.append(
        '<div class="card span6"><span class="arrow">↗</span><h3>Was Kunden sagen</h3>'
        '<p class="hint">Noch keine Daten — die nächste Analyse läuft montags um 05:00 UTC '
        'und füllt diesen Abschnitt automatisch.</p></div>')

TS_HTML = '\n'.join(_ts_teile)

TS_CSS = """
/* Pausche 04 Trends & Stimmen */
.tsk{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0 6px}
.tskb{background:#F2F0EB;border-radius:15px;padding:16px 18px}
.tskb .l{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.1px;color:#6E6A60}
.tskb .k{font-size:38px;font-weight:700;letter-spacing:-1.6px;line-height:1.1;margin-top:6px}
.tskb .s{font-size:13.5px;color:#6E6A60;margin-top:6px;line-height:1.35}
.tskb.gut .k{color:#1E9E5A}.tskb.gut .s{color:#1E9E5A;font-weight:600}
.tskb.schlecht .k{color:#C0392B}.tskb.schlecht .s{color:#C0392B;font-weight:600}
.tsgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:14px}
.tsc{background:#F2F0EB;border-radius:15px;overflow:hidden;text-decoration:none;color:inherit;
     display:flex;flex-direction:column;transition:transform .15s}
.tsc:hover{transform:translateY(-3px)}
.tsc img{width:100%;height:160px;object-fit:cover;display:block;background:#E7E4DC}
.tsc .ph{width:100%;height:160px;border-radius:0;font-size:15px}
.tcb{padding:10px 12px 13px;display:flex;flex-direction:column;gap:6px}
.tcc{font-size:14.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tcm{font-size:13px;color:#6E6A60;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tsc .pill{font-size:12.5px;padding:5px 11px;align-self:flex-start;white-space:normal;text-align:left}
.tsmom{display:flex;height:18px;border-radius:9px;overflow:hidden;background:#E7E4DC;margin:6px 0 8px}
.tsmom i{height:100%;display:block}
.tsmom .p{background:#1E9E5A}.tsmom .n{background:#B9B4A4}.tsmom .x{background:#C0392B}
.tonlbl{display:flex;justify-content:space-between;font-size:13.5px;color:#3E3B33;font-weight:600}
.tonlbl b{font-variant-numeric:tabular-nums}
.tonlbl span{display:flex;align-items:center;gap:6px}
.dotp,.dotn,.dotx{width:9px;height:9px;border-radius:50%;display:inline-block}
.dotp{background:#1E9E5A}.dotn{background:#B9B4A4}.dotx{background:#C0392B}
.kb{background:#F2F0EB;border-radius:15px;padding:13px 15px;font-size:14.5px;color:#3E3B33;
    margin-top:10px;line-height:1.5}
.kb .kbm{font-size:12px;color:#6E6A60;margin-bottom:5px;text-transform:uppercase;
    letter-spacing:.7px;font-weight:700}
details.tsdet{margin-top:14px;border-top:1px solid #E7E4DC;padding-top:11px}
details.tsdet>summary{font-size:14.5px;font-weight:700;color:#2A60FF;cursor:pointer}
details.tsdet[open]>summary{margin-bottom:8px}
.tstbl{width:100%;border-collapse:collapse;font-size:14.5px;margin-top:6px}
.tstbl th{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.9px;
    color:#6E6A60;padding:7px 8px;border-bottom:1px solid #E7E4DC}
.tstbl td{padding:8px;border-bottom:1px solid #F1F0EB}
.tstbl td.num,.tstbl th.num{text-align:right;font-variant-numeric:tabular-nums}
.tstbl a{color:#2A60FF;text-decoration:none;font-weight:600}
.tsakt li{margin:7px 0}
.tsintern{background:#E7E4DC;border-radius:15px;padding:16px 18px;margin-top:16px}
@media(max-width:860px){.tsk{grid-template-columns:1fr}
  .tsgrid{grid-template-columns:repeat(2,1fr)}.tsc img,.tsc .ph{height:140px}}
"""

PLAN_HTML = f"""
        {_HYP}
        {_sektion(1, 'Wo stehen wir?', f'<div class="span6">{KPI_HTML}</div>')}
        {_sektion(2, 'Was sollten wir ändern?', _PRIOS, 'Sortiert nach Evidenz, Wirkung und Aufwand')}
        {_sektion(3, 'Warum funktioniert es?', _MUSTER, _MUSTER_SUM, offen=False)}
        {_sektion(4, 'Was machen wir als Nächstes?', PLAN_JS_HTML + f"""<div class="card span6"><h3>So könnte eine gute Woche aussehen</h3>{_WOCHE}</div>""", 'Social-Plan KW 1–8 und Beispielwoche', offen=False)}
        {TS_SUM}
"""

S3_LEER = f"""
        <div class="card blue span6">
          <span class="arrow">↗</span>
          <h3>06 · Kampagnen — Wirkung der Kampagnen</h3>
          <p class="hint">Status: keine Datenquellen angebunden — dieser Abschnitt bleibt leer, bis Zugänge bestehen</p>
          <div class="heroRow"><div class="heroStats">
            <div class="hstat"><div class="v">–</div><div class="t"><span class="dot"></span>Aktive Kampagnen</div></div>
            <div class="hstat"><div class="v">–</div><div class="t"><span class="dot"></span>Reichweite je Kampagne</div></div>
            <div class="hstat"><div class="v">–</div><div class="t"><span class="dot"></span>App-Installationen</div></div>
            <div class="hstat"><div class="v">–</div><div class="t"><span class="dot"></span>Konversionen</div></div>
            <div class="hstat"><div class="v">–</div><div class="t"><span class="dot"></span>Kosten je Ergebnis</div></div>
            <div class="hstat"><div class="v">–</div><div class="t"><span class="dot"></span>ROI</div></div>
          </div></div>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Warum keine Zahlen?</h3>
          <p class="hint">Die geforderten Kampagnen-Kennzahlen liegen hinter diesen Zugängen:</p>
          <ul class="bul">
            <li><b>Meta Ads Manager / Marketing API</b> — Reichweite, Impressions, CPM, Conversions, Spend je Kampagne. Benötigt Werbekonto-ID und Zugriffsrecht (EDEKA vermarktet selbst, wir haben keinen Account).</li>
            <li><b>Instagram Insights-API</b> — Reichweite, Wiedergaben, Speicherungen je Beitrag. Nur für eigene, autorisierte Konten.</li>
            <li><b>App-Analytics</b> (Adjust/Firebase/App Store Connect) — Installationen, Öffnungen, In-App-Aktionen.</li>
            <li><b>Web-Tracking</b> — Klicks, UTM, Conversions im Shop. Aktuell keine UTM-Daten in den Social-Links vorhanden.</li>
            <li><b>Meta Pixel / Conversions API</b> — Wirkung auf Anmeldungen und Newsletter-Registrierungen.</li>
          </ul>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Vorhandene Näherungs-Indikatoren</h3>
          <p class="hint">Was ohne Zugänge bereits als Impact-Signal dient</p>
          <div class="catrow"><div class="c1">Organische Interaktionen, 30 Tage</div><div class="c2">{de(CUR_I)}</div></div>
          <div class="catbar"><div style="width:100%"></div></div>
          <div class="catrow"><div class="c1">Beiträge, 30 Tage</div><div class="c2">{de(CUR_N)}</div></div>
          <div class="catbar"><div style="width:100%"></div></div>
          <div class="catrow"><div class="c1">Profile mit Aktivität</div><div class="c2">{N_AKTIV30} / {de(N_KONTEN)}</div></div>
          <div class="catbar"><div style="width:{PCT_AKTIV:.0f}%"></div></div>
          <div class="catrow"><div class="c1">Laufende Werbeanzeigen (EDEKA, Ad Library)</div><div class="c2">{ads.get('edeka', {}).get('own', '–')}</div></div>
          <div class="catbar"><div style="width:40%"></div></div>
          <p class="hint" style="margin-top:10px">Das ersetzt keine Kampagnenmessung, zeigt aber Aktivität und Sichtbarkeit.</p>
        </div>
      """
S3_HTML = KAMP_HTML or S3_LEER
S3_TAB = ('''<span class="tab2" data-s="s3" onclick="sec('s3',this)">06 Kampagnen<small class="tabd">Was Social schon bewirkt hat</small></span>''' if KAMP_HTML
          else '''<span class="tab2 dim" data-s="s3" onclick="sec('s3',this)">06 Kampagnen<small class="tabd">noch ohne Daten · Zugang nötig</small></span>''')

PLAN_CSS_EXTRA = """
.eyebrow{display:block;font-size:13px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:rgba(255,255,255,.9);margin-bottom:10px}
.card.blue h3.headline{font-size:36px;line-height:1.06;font-weight:700;letter-spacing:-1.2px;margin:0 0 10px;padding-right:0;color:#fff}
.zielzeile{font-size:14px;color:rgba(255,255,255,.95);display:flex;flex-wrap:wrap;gap:8px;align-items:center;line-height:1.4}
.ziele{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.zlbl{font-size:13px;letter-spacing:1px;font-weight:600;color:#6E6A60;text-transform:uppercase;margin-right:2px}
.ziel{font-size:13px;font-weight:600;padding:6px 12px;border-radius:999px;background:#fff;color:#16150F;white-space:nowrap}
.ziel.light{background:#fff;color:#16150F}
.pill{display:inline-block;font-size:13px;font-weight:600;padding:6px 12px;border-radius:999px;white-space:nowrap;background:#fff;color:#16150F;line-height:1.3}
.pill.gut{background:#2A60FF;color:#fff;box-shadow:none}
.pill.mittel{background:#fff;color:#16150F}
.pill.schwach{background:#C9D6FF;color:#16150F;box-shadow:none}
.pill.info{background:#fff;color:#3E3B33}
.pill.vgl{white-space:normal;color:#3E3B33;text-align:left}
.vkgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.vk{background:#F2F0EB;border-radius:15px;padding:24px;display:flex;flex-direction:column;gap:12px;min-width:0}
.vkt{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#6E6A60}
.vkp{display:flex;flex-wrap:wrap;gap:6px;align-items:flex-start}
.vkz{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-top:2px}
.vkz b{font-size:76px;line-height:1;font-weight:700;letter-spacing:-2.5px;color:#16150F}
.vkz span{font-size:15px;font-weight:600;color:#3E3B33}
.z-gut,.z-mittel,.z-schwach{color:#16150F}
.vks{font-size:15px;line-height:1.45;color:#3E3B33;margin-top:auto}
.tbar{position:relative;background:#fff;height:14px;border-radius:7px;overflow:hidden;min-width:140px}
.tnorm{position:absolute;top:0;bottom:0;width:2px;background:#16150F}
.berl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.bz{background:#fff;border-radius:15px;padding:18px 20px;display:flex;flex-direction:column;gap:6px}
.bz .bl{font-size:13px;color:#6E6A60;font-weight:600;text-transform:uppercase;letter-spacing:.7px}
.bz b{font-size:32px;font-weight:700;letter-spacing:-1.4px;color:#16150F}
.bz .bs{font-size:13.5px;color:#6E6A60;line-height:1.5}
.intern{border:0}
.intag{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;background:#fff;color:#16150F;padding:5px 12px;border-radius:999px;margin-bottom:10px}
.intag.light{background:#fff;color:#16150F}
.kwgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.kw{background:#fff;border-radius:15px;padding:18px;display:flex;flex-direction:column;gap:8px}
.kwh{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.kwh b{font-size:16px;font-weight:700;color:#16150F}
.kwh span{font-size:13px;color:#6E6A60}
.kwa{font-size:15px;font-weight:600;color:#16150F;line-height:1.4}
.kwf{font-size:13.5px;color:#6E6A60}
.kwi{margin-top:auto;background:#F2F0EB;border-radius:12px;padding:12px 14px;font-size:14.5px;line-height:1.5;color:#3E3B33}
.kwm{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.kamp{display:flex;flex-direction:column;gap:10px}
.kmeta{font-size:13px;color:#6E6A60;font-weight:600}
.card.kamp h3{font-size:20px;letter-spacing:-.5px}
.kwerte{display:flex;flex-direction:column;gap:10px}
.kz{display:flex;flex-direction:column;gap:2px}
.kz b{font-size:32px;color:#2A60FF;letter-spacing:-1.4px;font-weight:700}
.kz span{font-size:14px;color:#3E3B33;line-height:1.4}
.kbez{font-size:13.5px;background:#fff;color:#16150F;border-radius:999px;padding:6px 12px;font-weight:600;align-self:flex-start}
@media(max-width:1250px){.vkgrid,.kwgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.berl{grid-template-columns:1fr}}
@media(max-width:760px){.vkgrid,.kwgrid{grid-template-columns:1fr}.card.blue h3.headline{font-size:22px}.vkz b{font-size:56px;letter-spacing:-2px}.card.kamp h3{font-size:18px}}
"""

PLAN_CSS = """
/* --- 00 Was jetzt tun --- */
.kurz{font-size:16px;line-height:1.55;margin:6px 0 18px;max-width:980px;color:#fff}
.sechead{background:transparent;border:0;box-shadow:none;padding:30px 0 2px}
.sechead h3{font-size:44px;line-height:1.05;font-weight:700;letter-spacing:-1.5px;margin:0 0 8px}
.sechead .hint{max-width:900px}
.hebel{display:flex;flex-direction:column;gap:14px}
.hebel h3{font-size:36px;line-height:1.05;font-weight:700;letter-spacing:-1.2px;margin:0;padding-right:0}
.hpills{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.hnr{width:32px;height:32px;border-radius:50%;background:#2A60FF;color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center;font-size:15px;flex:0 0 auto}
.hlbl{display:block;font-size:13px;letter-spacing:1px;font-weight:600;color:#6E6A60;text-transform:uppercase;margin-bottom:5px}
.hwarum{font-size:15px;line-height:1.5;color:#3E3B33}
.htun{background:#fff;border-radius:15px;padding:14px 16px;font-size:15px;line-height:1.5;color:#3E3B33}
.hwer{margin-top:auto;font-size:13px;color:#6E6A60;font-weight:600;padding-top:4px}
.hblock{background:#2A60FF;border-radius:22px;margin:2px 10px 0;padding:22px 24px;display:flex;flex-direction:column;gap:15px}
.brow{display:flex;flex-direction:column;gap:7px}
.bhead{display:flex;justify-content:space-between;gap:14px;font-size:14.5px;font-weight:600;color:#fff;line-height:1.3}
.bhead b{font-weight:700;white-space:nowrap}
.btrack{height:22px;border-radius:11px;background:rgba(255,255,255,.45);overflow:hidden}
.bfill{height:100%;min-width:6px;border-radius:11px;background:#FFF8E6}
.bfill.bad{background:rgba(255,255,255,.55)}
.combos{display:flex;flex-direction:column;gap:6px;margin-top:8px}
.combo{background:#fff;border:0;border-radius:12px;padding:8px 12px;font-size:14px;display:flex;justify-content:space-between;gap:10px;align-items:center;color:#16150F}
.combo i{font-style:normal;font-weight:700;color:#16150F;white-space:nowrap}
.combo i.gut{color:#2A60FF}
.combo i.schwach{color:#3E3B33}
.badge{display:inline-block;font-size:13px;font-weight:600;padding:5px 12px;border-radius:999px;white-space:nowrap}
.badge.green{background:#2A60FF;color:#fff}
.badge.amber{background:#fff;color:#3E3B33}
.badge.red{background:#C9D6FF;color:#16150F}
.badge.grey{background:#E7E4DC;color:#6E6A60}
.tfill{height:100%;border-radius:7px}
.tfill.green{background:#2A60FF}
.tfill.amber{background:rgba(42,96,255,.5)}
.tfill.red{background:#C9D6FF}
.tfill.grey{background:#E7E4DC}
.themtab td{padding:13px 9px}
.woche{display:flex;flex-direction:column}
.wrow{display:grid;grid-template-columns:76px 120px minmax(0,1fr);gap:10px;align-items:baseline;padding:13px 0;border-bottom:1px solid #2E2C25}
.woche .wrow:last-child{border-bottom:0}
.wtag{font-size:15px;font-weight:700;color:#16150F}
.wzeit{font-size:15px;font-weight:600;color:#2A60FF}
.wwas{font-size:15px;color:#3E3B33;line-height:1.4}
.wwas em{display:block;font-style:normal;font-size:13px;color:#6E6A60;margin-top:2px}
.glossar li{margin:9px 0;line-height:1.45}
@media(max-width:1250px){.span4{grid-column:span 2}}
@media(max-width:760px){
  .span4{grid-column:span 1}
  .kurz{font-size:15px}
  .sechead h3{font-size:30px;letter-spacing:-1px}
  .hebel h3{font-size:26px}
  .hblock{margin:2px 4px 0;padding:16px}
  .bhead{font-size:14px;flex-wrap:wrap;gap:4px 10px}
  .wrow{grid-template-columns:76px minmax(0,1fr);gap:4px 10px}
  .wwas{grid-column:1/-1}
  .tw table.themtab{min-width:0}
  .themtab th:nth-child(2),.themtab td:nth-child(2),.themtab th:nth-child(3),.themtab td:nth-child(3){display:none}
  .themtab td,.themtab th{padding:10px 5px}
  .badge{font-size:11px;padding:3px 7px}
}
"""

# Klartext-Überschriften für Tab 02
THEMEN_HEAD = (f"{esc(_TH_BEST[0]['thema'])} kommt {_mal(_TH_BEST[0]['med'], _TH_WORST['med'])} besser an als {esc(_TH_WORST['thema'])}"
               if _TH_BEST and _TH_WORST else 'Themenanalyse nach Caption')
FORMAT_HEAD = (f"{esc(_FMT_BASE['label'])} ist am verlässlichsten, {esc(_FMT_BONUS['label'])} {'bringen' if _FMT_BONUS['label'].endswith('s') else 'bringt'} die Glückstreffer"
               if _FMT_BASE and _FMT_BONUS and _FMT_BASE is not _FMT_BONUS else 'Leistung nach Format')
TAG_HEAD = f"Am besten: {_WD_BEST['label']}" if _WD_BEST else 'Beste Wochentage'
ZEIT_HEAD = f"Am besten: {_HR_BEST[0]['h']} Uhr, nicht {_HR_VOLL['h']} Uhr" if _HR_BEST and _HR_VOLL and _HR_BEST[0]['h'] != _HR_VOLL['h'] else 'Beste Uhrzeiten'

NAVCSS = """
.subline{margin:18px 0 12px;font-size:22px;line-height:1.4;font-weight:500;color:#3E3B33;max-width:760px}
.hypt{flex:1 1 100%;order:3;font-size:24px;font-weight:700;letter-spacing:-.6px;line-height:1.2;color:#16150F}
.hyps{order:4!important;font-weight:500!important;color:#3E3B33!important}
@media(max-width:760px){.subline{font-size:17px;margin-top:12px}.hypt{font-size:19px}}

/* Akkordeons */
details>summary{list-style:none;cursor:pointer}
details>summary::-webkit-details-marker{display:none}
.acc{grid-column:1/-1;border-top:1px solid #E7E4DC}
.acc>summary.frage{display:flex;align-items:center;gap:14px;padding:26px 0 18px}
.ftx{display:flex;flex-direction:column;gap:2px;flex:1 1 auto;min-width:0}
.fti{font-size:44px;font-weight:700;letter-spacing:-1.5px;line-height:1.05}
.fsu{font-size:15px;color:#6E6A60;font-weight:500}
.chev{flex:0 0 auto;width:36px;height:36px;border-radius:50%;background:#F2F0EB;position:relative}
.chev::after{content:"";position:absolute;left:50%;top:45%;width:9px;height:9px;border-right:2px solid #16150F;border-bottom:2px solid #16150F;transform:translate(-50%,-50%) rotate(45deg);transition:transform .2s}
details[open]>summary .chev::after{transform:translate(-50%,-20%) rotate(225deg)}
.accg{padding-bottom:24px}
.hyp>summary{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.hyps{flex:1 1 100%;font-size:16px;font-weight:600;line-height:1.4;color:#16150F;order:3}
.hyp>summary .chev{margin-left:auto}
.hyp[open] .hypg{margin-top:16px}
.hev{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#6E6A60}
.dot{width:8px;height:8px;border-radius:50%;flex:0 0 auto}.d-stark{background:#2A60FF}.d-mittel{background:#9DB4FF}.d-begrenzt{background:#fff;border:1.5px solid #8A867C}
.footer>summary{font-weight:700;color:#16150F;font-size:15px}
.footer[open]>summary{margin-bottom:10px}
@media(max-width:760px){.fti{font-size:28px;letter-spacing:-.8px}.fsu{font-size:13px}.acc>summary.frage{padding:20px 0 12px;gap:10px}.hyps{font-size:15px}}

/* Executive Overview */
.tabsep{align-self:center;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#8A867C;padding:0 4px 0 10px;flex:0 0 auto}
.frage{display:flex;align-items:flex-start;gap:14px;padding-top:26px!important}
.fnr{flex:0 0 auto;width:40px;height:40px;border-radius:50%;background:#16150F;color:#fff;font-size:18px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:4px}
.hyp{background:#fff!important;border:1.5px solid #16150F!important}
.hyph{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}
.eyebrow2{font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6E6A60}
.hypg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.hypc{border-radius:12px;padding:16px;display:flex;flex-direction:column;gap:6px;font-size:14px;line-height:1.45;color:#3E3B33}
.hypc b{font-size:13px;color:#16150F}
.hypc.ok{background:#E7EDFF}.hypc.open{background:#F2F0EB}.hypc.next{background:#F2F0EB}
.ev{display:inline-block;font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px;white-space:nowrap}
.ev-stark{background:#2A60FF;color:#fff}.ev-mittel{background:#C9D6FF;color:#16150F}.ev-begrenzt{background:#fff;color:#3E3B33;border:1px dashed #8A867C}
.ev.au{background:#fff;color:#3E3B33}
.hev{display:flex;flex-wrap:wrap;gap:6px}
.htd dl{margin:0;display:flex;flex-direction:column;gap:2px}
.htd dt{font-size:11px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#6E6A60;margin-top:8px}
.htd dd{margin:0;font-size:13.5px;line-height:1.5;color:#3E3B33}
.hbsp{display:block;background:#fff;border-radius:10px;padding:10px 12px;font-size:13px;line-height:1.4;color:#16150F;text-decoration:none;margin-top:4px}
.hbsp span{color:#2A60FF;font-weight:600;white-space:nowrap}
.hbsp:hover{text-decoration:none;outline:2px solid #2A60FF}
.mgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.mz{background:#fff;border-radius:12px;padding:16px;display:flex;flex-direction:column;gap:4px}
.mz .ml{font-size:13px;font-weight:600;color:#3E3B33}.mz b{font-size:34px;letter-spacing:-1px;line-height:1.1}.mz .mv{font-size:13px;color:#6E6A60}
.mbsp{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
@media(max-width:1100px){.hypg,.mgrid,.mbsp{grid-template-columns:1fr}}
@media(max-width:760px){.fnr{width:32px;height:32px;font-size:15px}.tabsep{display:none}}

/* Hebel als kompakte Kacheln */
.hgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;align-items:start}
.ht{background:#F2F0EB;border-radius:15px;padding:22px;display:flex;flex-direction:column;gap:14px;min-width:0}
.hth{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.ht .hnr{width:28px;height:28px;border-radius:50%;background:#2A60FF;color:#fff;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:0 0 auto}
.htz{font-size:11.5px;font-weight:600;color:#6E6A60;text-align:right;line-height:1.3;min-width:0;min-height:30px}
.htt{font-size:18px;font-weight:700;line-height:1.2;letter-spacing:-.3px;min-height:44px}
.htn{display:flex;flex-direction:column;gap:2px}
.htn b{font-size:52px;font-weight:700;letter-spacing:-2px;line-height:1;white-space:nowrap}
.htn span{font-size:13px;font-weight:600;color:#3E3B33;min-height:34px;line-height:1.3}
.hbs{display:flex;flex-direction:column;gap:8px}
.hbh{display:flex;justify-content:space-between;gap:8px;font-size:12px;font-weight:600;color:#3E3B33;margin-bottom:4px}
.hbh span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.hbh b{color:#16150F;white-space:nowrap}
.hbt{height:8px;border-radius:4px;background:#fff;overflow:hidden}
.hbf{height:8px;border-radius:4px;background:#2A60FF}.hbf.s{background:#B8B3A7}
.hta{font-size:14px;font-weight:600;line-height:1.35;min-height:38px}
.htd summary{display:inline-block;list-style:none;cursor:pointer;background:#fff;border-radius:999px;padding:9px 14px;font-size:13px;font-weight:600}
.htd summary::-webkit-details-marker{display:none}
.htd[open] summary{margin-bottom:10px}
.htd p{margin:0 0 8px;font-size:13.5px;line-height:1.5;color:#3E3B33}
.htd p b{color:#16150F}
.htd .htw{font-size:12px;color:#6E6A60}
@media(max-width:1250px){.hgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.hgrid{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scroll-padding-left:16px;gap:10px;margin:0 -16px;padding:0 16px 6px;scrollbar-width:none;-webkit-overflow-scrolling:touch}.hgrid::-webkit-scrollbar{display:none}.ht{flex:0 0 84%;scroll-snap-align:start}.htt,.htn span,.hta{min-height:0}.hgrid .ht:last-child{margin-right:16px}}

/* KPI-Karten Variante B */
.vkgrid{align-items:stretch}
.vk{gap:16px!important}
.vkh{display:flex;justify-content:space-between;align-items:center;gap:8px}
.vkt{font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#6E6A60}
.vku{font-size:13px;font-weight:700;white-space:nowrap}
.u-gut{color:#2A60FF}.u-mittel,.u-schwach{color:#3E3B33}
.vkz{display:flex;flex-direction:column;align-items:flex-start;gap:4px;margin:0!important}
.vkz b{font-size:56px!important;letter-spacing:-2px!important;line-height:1;white-space:nowrap;color:#16150F!important}
.vkz span{font-size:14px;font-weight:600;color:#3E3B33}
.kbs{display:flex;flex-direction:column;gap:8px}
.kb{display:grid;grid-template-columns:74px minmax(0,1fr) 48px;align-items:center;gap:8px;font-size:12.5px;font-weight:600}
.kbl{color:#3E3B33}.kbw{text-align:right;color:#16150F}
.kbt{height:10px;border-radius:5px;background:#fff;overflow:hidden}
.kbf{height:10px;border-radius:5px}.kbf.g{background:#2A60FF}.kbf.s{background:#B8B3A7}
.vks{font-size:14px!important;line-height:1.4;color:#3E3B33;margin-top:0!important}

/* --- Navigation: sticky + mobil als wischbare Leiste --- */
.tabd{display:none!important}
.top{position:sticky;top:0;z-index:50;margin:-36px -40px 0;padding:22px 40px 14px;background:rgba(255,255,255,.94);-webkit-backdrop-filter:saturate(1.4) blur(10px);backdrop-filter:saturate(1.4) blur(10px);border-radius:28px 28px 0 0;flex-wrap:nowrap;transition:padding .2s}
.top.scrolled{padding-top:12px;padding-bottom:12px;border-radius:0;box-shadow:0 1px 0 #ECEAE4}
.navleft{flex-wrap:nowrap;min-width:0;flex:1 1 auto}
.tabs2{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;scroll-snap-type:x proximity;max-width:100%}
.tabs2::-webkit-scrollbar{display:none}
.tab2{scroll-snap-align:start;flex:0 0 auto}
.meta{flex:0 0 auto}
.hero{padding-top:34px}
.hebel{align-self:start}
.eybst{display:none}
@media(max-width:1100px){.meta{display:none}.eybst{display:inline}}
@media(max-width:760px){
  .top{margin:-20px -16px 0;padding:14px 16px 10px;border-radius:22px 22px 0 0;gap:10px}
  .top.scrolled{padding-top:10px;padding-bottom:10px}
  .logo{width:40px;height:40px;font-size:18px}
  .tabs2{width:auto;flex:1 1 auto;padding:4px;gap:4px;mask-image:linear-gradient(90deg,#000 85%,transparent);-webkit-mask-image:linear-gradient(90deg,#000 85%,transparent)}
  .tab2{padding:9px 14px;font-size:14px;min-height:40px}
  .tabs2.end{mask-image:none;-webkit-mask-image:none}
  .h1{font-size:40px!important;letter-spacing:-1.4px!important}
  .main{padding:20px 16px 36px!important}
}
/* Kein Rahmen: volle Breite auf allen Geräten */
body{padding:0!important;background:#fff!important}
.main{border-radius:0!important}
.top,.top.scrolled{border-radius:0!important}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EDEKA · Social Media &amp; Marketing Intelligence</title>
<style>{CSS}</style></head>
<body><div class="app">
  <div class="main">
    <nav class="top">
      <div class="navleft">
        <span class="logo">E</span>
        <div class="tabs2">
        <span class="tab2 on" data-s="s0" onclick="sec('s0',this)">Übersicht</span><span class="tabsep">Analyse</span>
        <span class="tab2" data-s="s1" onclick="sec('s1',this)">01 Überblick<small class="tabd">Kennzahlen auf einen Blick</small></span>
        <span class="tab2" data-s="s2" onclick="sec('s2',this)">02 Inhalte<small class="tabd">Themen, Formate, Zeiten, Rankings</small></span>
        <span class="tab2" data-s="s4" onclick="sec('s4',this)">03 Wettbewerb<small class="tabd">Anzeigen von REWE, Lidl &amp; Co.</small></span>
        {TS_TAB}
        <span class="tab2" data-s="s5" onclick="sec('s5',this)">05 Details<small class="tabd">Alle Erkenntnisse &amp; Risiken</small></span>
        {S3_TAB}
        </div>
      </div>
      <span class="meta">{META_TEXT}</span>
    </nav>
    <div class="hero">
      <span class="eyb">Social Check · EDEKA<span class="eybst"> · {STAND}</span></span>
      <h1 class="h1">Wissen, was wirkt.</h1>
      <p class="subline">Aus Instagram-Daten werden klare Empfehlungen für besseres Marketing.</p>
    </div>

    <!-- 00 WAS JETZT TUN -->
    <div id="s0" class="sec">
      <div class="grid">{PLAN_HTML}
      </div>
    </div>

    <!-- 01 OVERVIEW -->
    <div id="s1" class="sec" style="display:none">
      <div class="grid">
        <div class="card blue span6">
          <span class="arrow">↗</span>
          <h3>01 · Überblick</h3>
          <p class="hint">Hochlevel-Kennzahlen über alle erfassten Instagram-Profile · Datenstand {STAND}</p>
          <div class="heroRow">
            <div class="heroStats wide">
              <div class="hstat"><div class="v">{de(N_KONTEN)}</div><div class="t"><span class="dot"></span>Instagram-Profile</div><div class="s">von 222 erfassten Konten</div></div>
              <div class="hstat"><div class="v">{de(N_FOLLOWER)}</div><div class="t"><span class="dot"></span>Follower gesamt</div><div class="s">über alle Profile</div></div>
              <div class="hstat"><div class="v">{de(OER_MED, 1)}</div><div class="t"><span class="dot"></span>Reaktionen pro 100 Follower</div><div class="s">typischer Beitrag (Median-ER {de(OER_MED, 2)} %)</div></div>
              <div class="hstat"><div class="v">{de(N_POSTS)}</div><div class="t"><span class="dot"></span>Analysierte Beiträge</div><div class="s">je Konto die letzten 12 Beiträge</div></div>
              <div class="hstat"><div class="v">{de(O_INT_POST)}</div><div class="t"><span class="dot"></span>Ø Interaktionen je Beitrag</div><div class="s">Likes + Kommentare</div></div>
              <div class="hstat"><div class="v">{N_AKTIV30}</div><div class="t"><span class="dot"></span>Aktive Profile (30 Tage)</div><div class="s">{PCT_AKTIV:.0f} % aller Profile</div></div>
              <div class="hstat"><div class="v">{de(mov_med[0]['er_med'], 1)}</div><div class="t"><span class="dot"></span>Bestes Profil (Reaktionen / 100 F.)</div><div class="s">@{esc(mov_med[0]['handle'])} · {mov_med[0]['n_valid']} Beiträge</div></div>
              <div class="hstat"><div class="v">3</div><div class="t"><span class="dot"></span>Nationale Marken-Accounts</div><div class="s">@edeka · @edekakarriere · @dein.edeka</div></div>
            </div>
          </div>
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>{'Interaktionen je Beitrag nach Woche' if USE_NORM else 'Leistungsverlauf · 12 Wochen'}</h3>
          <p class="hint">{('Likes + Kommentare je Beitrag, normalisiert. Keine der 12 Wochen ist für alle {1} Konten vollständig abgedeckt (je Konto nur die letzten 12 Beiträge, vollständig erst ab {2}), deshalb keine absoluten Volumenwerte, die zwischen den Wochen vergleichbar wären.'.format(FULL_WEEKS, de(N_KONTEN), COVER_START.strftime('%d.%m.%Y')) if FULL_WEEKS == 0 else 'Likes + Kommentare je Beitrag, normalisiert. {0} der 12 Wochen sind für alle {1} Konten vollständig abgedeckt (vollständig ab {2}), deshalb ohne absolute Volumenwerte.'.format(FULL_WEEKS, de(N_KONTEN), COVER_START.strftime('%d.%m.%Y'))) if USE_NORM else 'Interaktionen (Likes + Kommentare) je Woche über alle Profile'}</p>
          {svg_line(wk_ipost if USE_NORM else wk_int, wk_lab)}
          <p class="hint" style="margin:10px 0 0">{'Peak {0} Interaktionen je Beitrag · aktuelle Woche {1} · {2} Beiträge'.format(f"{max(wk_ipost):,.0f}".replace(',', '.'), f"{wk_ipost[-1]:,.0f}".replace(',', '.'), de(wk_cnt[-1])) if USE_NORM else 'Peak {0} Interaktionen · aktuelle Woche {1} · {2} Beiträge'.format(de(max(wk_int)), de(wk_int[-1]), de(wk_cnt[-1]))}</p>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Follower-Wachstum</h3>
          <p class="hint">Vergleich der Snapshots</p>
          <x data-v="hist_growth" data-optional="1"></x>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Wochentrend</h3>
          <p class="hint">Interaktionen je Beitrag aus allen Snapshots</p>
          <x data-v="hist_trend" data-optional="1"></x>
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>Verfügbare Daten — und was fehlt</h3>
          <p class="hint">Transparenz über die tatsächlich messbaren Kennzahlen</p>
          <div class="avail">
            <div class="ok"><b>Verfügbar</b>
              <ul><li>Alle Instagram-Profile mit Handle, Name, Follower, Verifizierung</li>
              <li>Letzte 12 Beiträge je Profil: Likes, Kommentare, Datum, Format</li>
              <li>Engagement-Rate, Posting-Aktivität, Zeitmuster, Hashtags</li>
              <li>Laufende Werbeanzeigen über die Meta Ads Library (öffentlich)</li></ul></div>
            <div class="no"><b>Nicht verfügbar (keine API-Daten)</b>
              <ul><li>Reichweite &amp; Impressionen je Beitrag</li>
              <li>Wiedergaben der Reels, Shares, Saves, Story-Daten</li>
              <li>Follower-Wachstum über die Zeit (kein Historiendaten-Zugriff auf Fremdkonten)</li>
              <li>Kampagnen-, App- und Conversion-Daten (Meta Ads Manager, App-Analytics)</li>
              <li>Kosten und ROI je Kampagne</li></ul></div>
          </div>
          <p class="hint" style="margin-top:12px">Grund: Instagram liefert Reichweite/Impressionen nur über die Insights-API für die eigenen, autorisierten Konten. Für Wettbewerbs- und Fremdkonten gibt es diese Werte weder über die API noch über die Ad Library.</p>
        </div>
      </div>
    </div>

    <!-- 02 PROFILES & CONTENT -->
    <div id="s2" class="sec" style="display:none">
      <div class="grid">{EXPLORER_EXTRA}
        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>02 · Inhalte — Analyse je Profil</h3>
          <p class="hint">{de(N_KONTEN)} Profile · {N_AKTIV30} davon in den letzten 30 Tagen aktiv · Ranking nach Median-ER, getrennt nach Größenklassen (ab {RANK_MIN_FOLLOWER} Followern, mindestens {MOV_MIN} Beiträge mit Like-Wert)</p>
          <div class="miniRow">
            <div class="mini"><span>{de(N_KONTEN)}</span>Profile gesamt</div>
            <div class="mini"><span>{N_AKTIV30} ({PCT_AKTIV:.0f} %)</span>aktiv in 30 Tagen</div>
            {SEG_KPIS}
          </div>
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>Rankings</h3>
          <p class="hint">Wechsle zwischen Profilen, besten/schwächsten Beiträgen und Aktivität</p>
          <div class="tabs">
            <button class="tab on" onclick="tab('u1',this)">Profile nach Median-ER</button>
            <button class="tab" onclick="tab('u2',this)">Top 15 Beiträge</button>
            <button class="tab" onclick="tab('u3',this)">Schwächste Beiträge</button>
            <button class="tab" onclick="tab('u4',this)">Aktivste Profile</button>
          </div>
          <div id="u1" class="panel">
            <div class="tabs segtabs">
              <button class="tab on" onclick="seg('g0',this)">{'< 2.000 Follower'}</button>
              <button class="tab" onclick="seg('g1',this)">2.000 bis 10.000 Follower</button>
              <button class="tab" onclick="seg('g2',this)">{'> 10.000 Follower'}</button>
            </div>
            {SEG_PANELS}
          </div>
          <div id="u2" class="panel" style="display:none">
            {TW_TOP}
          </div>
          <div id="u3" class="panel" style="display:none">
            {TW_WORST}
            <p class="hint" style="margin-top:10px">Nur Beiträge mit Like-Wert aus Profilen ab 500 Followern. {de(N_NO_LIKES)} Beiträge ohne Like-Wert (0 oder 1 Like, vom Anbieter nicht geliefert) sind in ER, Rankings und Empfehlungen ausgeblendet.</p>
          </div>
          <div id="u4" class="panel" style="display:none">
            {TW_AKTIV}
          </div>
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>{THEMEN_HEAD}</h3>
          <p class="hint">{de(N_KLASSIFIZIERT)} von {de(N_POSTS)} Beiträgen automatisch einer Kategorie zugeordnet (LLM, eine Kategorie je Caption). Median-ER je Thema, Werte unter 20 Beiträgen grau als geringe Basis.</p>
          {themen_bars()}
          <p class="hint" style="margin-top:14px">Median-ER je Thema und Format (Zellen ab 10 Beiträgen, sonst –)</p>
          {matrix_html()}
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>Überflieger: Beiträge mit dem Dreifachen oder mehr des eigenen Normalwerts</h3>
          <p class="hint">Lift = Interaktionen des Beitrags (Likes + Kommentare) geteilt durch den Median der Interaktionen des eigenen Profils. Gezeigt: {len(ueberflieger)} Beiträge mit Lift ≥ 3 von Profilen mit mindestens {MOV_MIN} Beiträgen mit Like-Wert.</p>
          {TW_FLIEGER}
          <p class="hint" style="margin-top:10px"><b>Befund:</b> {FL_INSIGHT}</p>
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>{FORMAT_HEAD}</h3>
          <p class="hint">Ø Engagement-Rate je Format — Median daneben, weil einzelne Viral-Beiträge den Mittelwert verzerren</p>
          <div class="grid" style="gap:14px">{fmt_cards}</div>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>{TAG_HEAD}</h3>
          <p class="hint">Reaktionen pro 100 Follower je Wochentag, typischer Beitrag (Beiträge mit Follower-Daten)</p>
          {bars_h(WD_ROWS, 'label', 'med', lambda v: de(v, 2) + ' %', 7)}
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>{ZEIT_HEAD}</h3>
          <p class="hint">Reaktionen pro 100 Follower je Uhrzeit, typischer Beitrag (min. 40 Beiträge)</p>
          {bars_h(sorted(HR_ROWS, key=lambda r: -r['med'])[:8], 'h', 'med', lambda v: de(v, 2) + ' %', 8)}
          <p class="hint" style="margin-top:8px">Beitragsvolumen peaks: 18:00 ({de(next((r['n'] for r in HR_ROWS if r['h'] == 18), 0))} Beiträge), 10:00, 16:00</p>
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>Themen &amp; Hashtags</h3>
          <p class="hint">Häufigste Hashtags in den {de(N_POSTS)} analysierten Beiträgen</p>
          <div class="tagwrap">{''.join(f'<span class="tag">#{esc(t)} · {de(c)}</span>' for t, c in TOP_TAGS)}</div>
        </div>
      </div>
    </div>

    <!-- 03 CAMPAIGN IMPACT -->
    <div id="s3" class="sec" style="display:none">
      <div class="grid">{S3_HTML}</div>
    </div>

    <!-- 04 COMPETITOR -->
    <div id="s4" class="sec" style="display:none">
      <div class="grid">
        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>03 · Wettbewerb — Anzeigen der Konkurrenz</h3>
          <p class="hint">Laufende Werbeanzeigen aus der Meta Ads Library (Deutschland, aktiv), abgefragt am {STAND_ADS}</p>
          {TW_ADS}
          <p class="hint" style="margin-top:10px">Die Ad Library zeigt max. 20 Treffer je Abfrage — die Zahlen sind eine Untergrenze, kein Gesamtbestand. Ausgewertet wurden nur Anzeigen der eigenen Marken-Seiten (fremde Treffer wie Rabatt-Apps verwässern die Suche).</p>
        </div>

        {WEI_CARD}

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>Die stärksten Anzeigen der Wettbewerber · letzte 90 Tage</h3>
          <p class="hint">Auswahl aus der Meta Ads Library: aktive Anzeigen mit den größten Marken-Seiten, stärkster Botschaft und aktuellem Startdatum. HOOK = reißerischer Einstieg, WARUM ES FUNKTIONIERT = Analyse nach Format, Botschaft und Mechanik.</p>
          {ad_grid}
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Was die Konkurrenz macht</h3>
          <ul class="bul">{KONK_BULLETS}</ul>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Wettbewerbs-Framework</h3>
          {TW_FRAME}
          <p class="hint" style="margin-top:10px"><b>Einschränkung:</b> Die Meta Ads Library zeigt nur öffentliche Anzeigen (Seite, Laufzeit, Format, Text). Sie liefert <b>keine</b> Reichweiten-, Kosten- oder Performance-Werte der Konkurrenz.</p>
        </div>
      </div>
    </div>

    <!-- 04 TRENDS & STIMMEN -->
    <div id="s6" class="sec" style="display:none">
      <div class="grid">
        {TS_HTML}
      </div>
    </div>

    <!-- 05 INSIGHTS -->
    <div id="s5" class="sec" style="display:none">
      <div class="grid">
        <div class="card blue span6">
          <span class="arrow">↗</span>
          <h3>05 · Details — alle Erkenntnisse &amp; Empfehlungen</h3>
          <p class="hint">Automatisch abgeleitet aus {de(N_POSTS)} Beiträgen von {de(N_KONTEN)} Profilen</p>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Was funktioniert</h3>
          <ul class="bul">
            <li><b>Reels liefern die größten Ausreißer nach oben:</b> Ø ER {de(fmt_rows[0]['er'], 1)} % (Median {de(fmt_rows[0]['er_med'], 2)} %) gegenüber Foto {de(dict((r['key'], r) for r in fmt_rows).get('photo', {}).get('er', 0), 1)} %. Carousels haben den besten Median ({de(dict((r['key'], r) for r in fmt_rows).get('carousel', {}).get('er_med', 0), 2)} %) — sie performen konstanter, Reels liefern die Ausreißer nach oben.</li>
            <li><b>Beste Tage:</b> {TAGE_TEXT}.</li>
            <li><b>Beste Uhrzeiten:</b> {', '.join(f"{r['h']}:00 ({de(r['med'], 2)} %)" for r in best_hours)} — die Masse postet um 18:00, der Median sinkt dort jedoch (volle Timeline, mehr Konkurrenz).</li>
            <li><b>Stärkste Profile (Median):</b> {', '.join('@' + a['handle'] for a in mov_med[:3])} — {de(mov_med[0]['er_med'], 1)} %, {de(mov_med[1]['er_med'], 1)} %, {de(mov_med[2]['er_med'], 1)} % Median-ER.</li>
            {THEMEN_TEXT}
            <li><b>Häufigste Hashtags:</b> {', '.join('#' + t for t, c in TOP_TAGS[:5])}.</li>
          </ul>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Empfehlungen</h3>
          <ul class="bul">
            <li><b>Format-Mix:</b> {FMT_MED_BEST['label']} für Konstanz (bester Median {de(FMT_MED_BEST['er_med'], 2)} %, {de(FMT_MED_BEST['n'])} Beiträge), {FMT_P90_LABEL} für die Ausreißer nach oben (P90 {de(FMT_P90_VAL, 1)} %). Der Median entscheidet, welches Format der Standard ist.</li>
            <li><b>Zeitfenster:</b> {ZEIT_TEXT}.</li>
            <li><b>Nachbauen der Gewinner-Formate:</b> stärkster Beitrag stammt von @{esc(best_posts[0]['handle'])} mit {de(best_posts[0]['likes'])} Likes ({FMT_DE.get(best_posts[0].get('kind'), 'Reel')}), dahinter @{esc(best_posts[1]['handle'])} mit {de(best_posts[1]['likes'])}. Solche Kurz-Sketche vorproduziert über die Regionalgesellschaften teilen.</li>
            <li><b>Kampagnen-Lücke schließen:</b> Für 03 zuerst Meta-Ads-Zugriff (Ads Manager der EDEKA-Zentrale oder Test-Werbekonto) und UTM-Links in alle Bio-Verlinkungen.</li>
            <li><b>Datenlücken:</b> Reichweite/Impressionen nur über die Insights-API eigener Konten — für die eigene Wertmessung Instagram-Business-Accounts autorisieren.</li>
            <li><b>Wettbewerb:</b> Recruiting- und DCO-Anzeigen der Konkurrenz als Vorlage; die eigene WhatsApp-Community ist ein Differenzierungsmerkmal.</li>
          </ul>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Schwächen &amp; Risiken</h3>
          <ul class="bul">
            <li><b>Unter den Top-15:</b> {', '.join('@' + p['handle'] for p in worst_posts[:3])} — Beiträge mit {worst_posts[0]['likes']} Likes bei {de(worst_posts[0]['followers'])} Followern.</li>
            <li><b>{de(n_null_likes)} Beiträge ohne Like-Wert</b> — Like-Anzahl vom Datensatz-Anbieter nicht geliefert; betroffen sind v. a. kleine Märkte.</li>
            <li><b>Sparse Profiles:</b> {de(N_KONTEN - N_AKTIV30)} Profile hatten in 30 Tagen keinen Beitrag.</li>
            <li><b>Datensatz-Fenster:</b> je Konto nur die letzten 12 Beiträge — der 12-Wochen-Verlauf unterschätzt die Älteren automatisch.</li>
            <li><b>Wettbewerbsdaten:</b> Ad Library ohne Performance-Werte; kein Vergleich von Reichweite oder Kosten möglich.</li>
          </ul>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Nächste Schritte</h3>
          <ol class="steps">
            <li>Instagram Insights für autorisierte Konten anbinden → Reichweite, Wiedergaben, Speicherungen.</li>
            <li>Meta Marketing API für ein Werbekonto → 03 Campaign Impact füllen (Spend, CPM, Conversions).</li>
            <li>UTM-Parameter in alle Social-Links → Klicks und Conversions nach Kanal.</li>
            <li>App-Analytics (Firebase/Adjust) für Installationen und In-App-Aktionen.</li>
            <li>Wöchentlicher Autolauf: Beiträge neu ziehen und Verlauf als Zeitreihe fortschreiben.</li>
          </ol>
        </div>
      </div>
    </div>

    <details class="footer"><summary>Methodik &amp; Datenquellen</summary>
      <b>Methodik:</b> Engagement-Rate = (Likes + Kommentare) ÷ Follower × 100, gemittelt über die letzten 12 Beiträge je Profil;
      Profile ab 500 Followern und mindestens 5 Beiträgen im Ranking. Median zusätzlich zum Mittelwert, weil einzelne Viral-Beiträge verzerren.
      Aktivität = Beiträge in den letzten 30 Tagen (Datenstand {STAND}). Uhrzeiten in {TZ_LABEL} (deutsche Ortszeit, aus UTC umgerechnet).
      Wettbewerbsdaten: Meta Ads Library, Deutschland, Status „aktiv", Abfrage {STAND_ADS}, max. 20 Treffer je Marke.
      Quellen: Instagram-Profil- und Beitragsdaten, öffentlich · Census: {de(N_KONTEN)} berücksichtigte Profile von {de(N_GES)} erfassten Konten.
      Reichweite, Impressionen, Kampagnen- und App-Daten sind nicht Teil dieser Auswertung (siehe 06).
      Themenklassifikation: eine Kategorie je Caption, Modell gpt-4o-mini, Kategorien Angebot/Preis, Rezept/Food, Gesund/Bio/Protein, Humor/Team/Azubi, Region/Lieferant, Recruiting/Karriere, Gewinnspiel, Event/Aktion, Sonstiges. {ACC_TEXT}
      Datenaufbereitung: {de(N_AUSGESCHLOSSEN)} Konten ausgeschlossen (nicht in Deutschland bzw. kein EDEKA-Markt, siehe data/excluded_accounts.csv), {de(N_FREMDE_POSTS)} Beiträge fremder Owner entfernt (owner weder das Profil noch der EDEKA-Verbund), {de(N_NO_LIKES)} Beiträge ohne Like-Wert für ER- und Ranking-Auswertungen ausgeblendet ({de(N_POSTS_GUELTIG)} von {de(N_POSTS)} Beiträgen mit Like-Wert).
    </details>
  </div>
</div>
<script>{JS}</script>
<script src="static/render.js"></script>
</body></html>"""


# ---------------- v2-Layout (unveraendert vom Stand auf main) ----------------
V2_CSS = """
/* --- v2 tweaks --- */
.card{min-width:0}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px}
.tw table{min-width:640px}
.chartw{overflow-x:auto}
@media(max-width:760px){.chartw svg{min-width:560px}}
.heroStats{gap:0!important;overflow:hidden;min-width:0}
.heroStats .hstat{background:none;border:0;border-radius:0;border-left:1px solid rgba(255,255,255,.3);border-top:1px solid rgba(255,255,255,.3);margin:-1px 0 0 -1px;padding:16px 20px}
.heroRow{display:block}
@media(max-width:760px){
  .main{padding:20px 16px 36px}
  .top{gap:10px;padding-bottom:4px}
  .logo{width:44px;height:44px;font-size:20px}
  .tabs2{width:100%;padding:5px;gap:5px}
  .tab2{padding:7px 13px;font-size:13px}
  .tabd{display:none}
  .meta{padding:9px 15px;font-size:13px}
  .hero{padding:24px 0 6px}
  .eyb{font-size:12px;margin-bottom:10px}
  .card{padding:18px}
  .card h3{font-size:24px;letter-spacing:-.6px;padding-right:22px}
  .card.span2 h3,.card.span3 h3{font-size:19px}
  .card.blue h3{font-size:26px;letter-spacing:-.8px}
  .card .hint{font-size:14px}
  .kpi .k{font-size:56px;letter-spacing:-2px}
  .miniRow{grid-template-columns:1fr 1fr;gap:10px}
  .mini span{font-size:20px}
  .tw table{min-width:760px}
  .heroStats,.heroStats.wide{grid-template-columns:repeat(2,1fr)!important}
  .heroStats .hstat{padding:14px 12px}
  .hstat .v{font-size:21px}
  .hstat .t{font-size:12px;align-items:flex-start}
  .hstat .t .dot{margin-top:5px;flex:0 0 auto}
  .hstat .s{font-size:11px;word-break:break-word}
  .tab{white-space:nowrap}
  .adgrid{grid-template-columns:1fr}
  .footer{padding:20px}
  .avail .ok,.avail .no{padding:16px}
  .bul,.steps{font-size:14.5px}
}
"""
V3_CSS = """
/* --- v3 header + centering --- */
.main{margin:0 auto}
@media(max-width:1000px){.h1{font-size:60px;letter-spacing:-2.6px}}
@media(max-width:760px){.h1{font-size:44px;letter-spacing:-1.5px}}
"""
# ---------------- Shell + Views: Zahlen kommen per fetch aus data/dashboard.json ----------------
def _split_template(tpl):
    """Template in Teile zerlegen: Textstuecke und {ausdruck}-Positionen."""
    parts, i, n = [], 0, len(tpl)
    while i < n:
        c = tpl[i]
        if c == '{':
            if i + 1 < n and tpl[i + 1] == '{':
                parts.append('{'); i += 2; continue
            j, depth, q = i + 1, 0, None
            while j < n:
                ch = tpl[j]
                if q:
                    if ch == '\\':
                        j += 2; continue
                    if ch == q:
                        q = None
                else:
                    if ch in ('"', "'"):
                        q = ch
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        if depth == 0:
                            break
                        depth -= 1
                j += 1
            parts.append(('EXPR', tpl[i + 1:j])); i = j + 1
        elif c == '}' and i + 1 < n and tpl[i + 1] == '}':
            parts.append('}'); i += 2
        else:
            parts.append(c); i += 1
    return parts


def _eval_expr(expr, scope):
    """Ausdruck auswerten, inklusive Format-Spec ({x:.2f})."""
    try:
        return eval(expr, scope)
    except SyntaxError:
        pass
    i, depth, q, split = 0, 0, None, -1
    while i < len(expr):
        ch = expr[i]
        if q:
            if ch == '\\':
                i += 2; continue
            if ch == q:
                q = None
        else:
            if ch in ('"', "'"):
                q = ch
            elif ch in '([{':
                depth += 1
            elif ch in ')]}':
                depth -= 1
            elif ch == ':' and depth == 0:
                split = i
        i += 1
    if split > 0:
        val = eval(expr[:split], scope)
        spec = expr[split + 1:].strip()
        return format(val, spec) if spec else str(val)
    raise


def _tw(html_):
    if html_.count('<table') != html_.count('</table>'):
        return html_
    return html_.replace('<table', '<div class="tw"><table').replace('</table>', '</table></div>')


EXTRA_CSS = """
x[data-v]{display:contents}
.boot{display:none;max-width:640px;margin:60px auto;background:#F2F0EB;border:0;border-radius:15px;padding:26px;text-align:center;color:#6E6A60;font-size:15px}
body.loading .boot{display:block}
body.loading .grid,body.loading .footer{display:none}
"""

_parts = _split_template(TEMPLATE)
_shell, VIEWS, _k = [], {}, 0
for _p in _parts:
    if isinstance(_p, tuple):
        _expr = _p[1]
        _val = _eval_expr(_expr, globals())
        if _expr in ('CSS', 'JS'):
            _shell.append(_val)
        else:
            _key = 'v%d' % _k
            _k += 1
            VIEWS[_key] = _val
            _shell.append('<x data-v="%s"></x>' % _key)
    else:
        _shell.append(_p)
html_doc = ''.join(_shell)
assert html_doc.count('<table') == html_doc.count('</table>'), 'Tabelle defekt'
html_doc = _tw(html_doc)
html_doc = html_doc.replace('</style>', V2_CSS + V3_CSS + EXTRA_CSS + PLAN_CSS + PLAN_CSS_EXTRA + TS_CSS + NAVCSS + '</style>', 1)
html_doc = html_doc.replace('<body><div class="app">',
                            '<body class="loading"><div class="boot">Daten werden aktualisiert '
                            '&middot; bitte kurz warten.</div><div class="app">', 1)

# Snapshot zuerst anlegen, dann daraus auswerten
write_snapshot(posts)

# Historie-Auswertungen (erst ab 2 Snapshots sichtbar)
HIST_GROWTH, HIST_TREND = hist_views()

# Datensaetze schreiben
CLEAN = [{'id': q.get('url'), 'profil': q['handle'], 'likes': q.get('likes'),
          'kommentare': q.get('comments'), 'datum': q.get('taken_at'), 'format': q.get('kind'),
          'follower': q.get('followers'), 'likes_ok': bool(q.get('likes_ok')),
          'thema': q.get('thema'),
          'interaktionen': ((q.get('likes') or 0) + (q.get('comments') or 0)) if q.get('likes_ok') else None}
         for q in posts]
json.dump(CLEAN, open(os.path.join(DATA, 'posts_clean.json'), 'w'), ensure_ascii=False, indent=1)

if HIST_GROWTH:
    VIEWS['hist_growth'] = HIST_GROWTH
if HIST_TREND:
    VIEWS['hist_trend'] = HIST_TREND

DASH = {
    'generated_at': LAUF,
    'generated_iso': dt.datetime.now(BERLIN).isoformat(timespec='seconds'),
    'stand': STAND,
    'ads_abfrage': STAND_ADS,
    'kpi': {'profile': N_KONTEN, 'profile_ges': N_GES, 'follower': N_FOLLOWER,
            'beitraege': N_POSTS, 'beitraege_gueltig': N_POSTS_GUELTIG,
            'aktiv30': N_AKTIV30, 'median_er': round(OER_MED, 3), 'mean_er': round(OER, 3),
            'ausgeschlossen_konten': N_AUSGESCHLOSSEN, 'fremd_owner': N_FREMDE_POSTS,
            'ohne_like': N_NO_LIKES},
    'snapshots': len(history_dates()),
    'views': VIEWS,
}
json.dump(DASH, open(os.path.join(DATA, 'dashboard.json'), 'w'), ensure_ascii=False, indent=1)

open(os.path.join(SITE, 'index.html'), 'w').write(html_doc + '\n')
print("HTML:", os.path.join(SITE, 'index.html'), len(html_doc), "bytes | Views:", len(VIEWS))
print(f"Profile={N_KONTEN} Follower={N_FOLLOWER} Beiträge={N_POSTS} aktiv30={N_AKTIV30} ØER={OER:.1f}%")
print("Format-Reihenfolge:", [(r['label'], round(r['er'], 1), round(r['er_med'], 2)) for r in fmt_rows])
print("Snapshots:", len(history_dates()), "| Historie-Views:", bool(HIST_GROWTH), bool(HIST_TREND))

print('Bilder:', len(os.listdir(IMG)))
