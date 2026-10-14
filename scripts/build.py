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
        posts.append(q)
    accounts.append({
        'handle': h, 'nombre': p['nombre'] or h, 'followers': followers, 'tipo': p['tipo'],
        'n': len(plist), 'n_valid': n_valid,
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
for i, b in enumerate(best_posts[:12]):
    IMGMAP[b.get('image')] = dl(b.get('image'), f"b{i:02d}_{b['handle']}.jpg")
for i, b in enumerate(worst_posts[:8]):
    IMGMAP[b.get('image')] = dl(b.get('image'), f"w{i:02d}_{b['handle']}.jpg")

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
    dots = ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#2A60FF"/>' for x, y in pts)
    lab = ''
    for i, (x, y) in enumerate(pts):
        if i % 2 == 0 or i == len(pts) - 1:
            lab += f'<text x="{x:.1f}" y="{h-12}" font-size="10" fill="#8A90A0" text-anchor="middle">{labs[i]}</text>'
    peak = max(range(len(vals)), key=lambda i: vals[i])
    px, py = pts[peak]
    ann = f'<text x="{px:.1f}" y="{py-9:.1f}" font-size="11" font-weight="700" fill="#2A60FF" text-anchor="middle">{de(vals[peak])}</text>'
    return f"""<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none">
      <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#2A60FF" stop-opacity=".22"/><stop offset="100%" stop-color="#2A60FF" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="{area}" fill="url(#g1)"/>
      <polyline points="{poly}" fill="none" stroke="#2A60FF" stroke-width="2.5" stroke-linejoin="round"/>
      {dots}{ann}{lab}
    </svg>"""

def bars_v(items, valkey, labs, highlight=None, unit=''):
    mx = max([i[valkey] for i in items]) or 1
    out = []
    for i, it in enumerate(items):
        v = it[valkey]
        hh = max(6, v / mx * 132)
        blue = (highlight is not None and i == highlight)
        out.append(f"""<div class="bcol">{'<span class="bval">' + de(v, 1 if isinstance(v, float) else 0) + '</span>' if blue else ''}
          <div class="bbar" style="height:{hh:.0f}px;background:{'#2A60FF' if blue else '#E3E6EB'}"></div>
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

fmt_cards = ''.join(f"""<div class="card kpi span2"><span class="arrow">↗</span>
  <div class="l">{esc(r['label'])}</div>
  <div class="k">{de(r['er_med'], 2)} %</div>
  <div class="delta grey">Median · Ø {de(r['er'], 1)} % · {de(r['n'])} Beiträge · {de(r['mean_likes'])} Likes</div></div>"""
  for r in fmt_rows)


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#F2F3F5;color:#333;font:14px/1.5 Poppins,Inter,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
.app{min-height:100vh}
.side{width:74px;background:#fff;box-shadow:1px 0 6px rgba(0,0,0,.05);display:flex;flex-direction:column;align-items:center;padding:18px 0;gap:14px;position:sticky;top:0;height:100vh}
.logo{width:38px;height:38px;border-radius:11px;background:#2A60FF;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;margin-bottom:10px}
.sic{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;color:#8A90A0;cursor:pointer;font-size:15px}
.sic.on{background:#2A60FF;color:#fff}
.sic:hover{background:#EEF2FF;color:#2A60FF}
.main{flex:1;padding:0 26px 46px;max-width:1500px}
.top{min-height:70px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 0}
.top h1{font-size:16.5px;font-weight:600;margin:0;letter-spacing:-.2px}
.top h1 span{font-weight:600}
.tabs2{display:flex;gap:6px;margin-left:14px;flex-wrap:wrap}
.tab2{padding:7px 13px;border-radius:8px;font-size:12.5px;color:#6B7280;cursor:pointer;font-weight:500;white-space:nowrap}
.tab2.on{background:#E7EDFF;color:#2A60FF;font-weight:600}
.spacer{flex:1}
.meta{font-size:12.5px;color:#8A90A0}
.avatar{width:32px;height:32px;border-radius:50%;background:#2A60FF;color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:20px}
.card{background:#fff;border:1px solid #E4E8F0;border-radius:14px;box-shadow:none;padding:22px;position:relative}
.card.blue{background:linear-gradient(135deg,#1B49D6 0%,#2A60FF 55%,#5B8CFF 100%);color:#fff;border:none;box-shadow:0 8px 22px rgba(42,96,255,.25)}
.card h3{margin:0 0 4px;font-size:15.5px;font-weight:700}
.card .hint{margin:0 0 16px;font-size:12.5px;color:#8A90A0}
.card.blue .hint{color:rgba(255,255,255,.85)}
.arrow{position:absolute;top:20px;right:20px;color:#B9BFCC;font-size:15px}
.card.blue .arrow{color:rgba(255,255,255,.8)}
.muted{color:#9AA0AE}
.segtabs{margin-bottom:10px}
.span6{grid-column:span 6}.span4{grid-column:span 4}.span3{grid-column:span 3}.span2{grid-column:span 2}
.kpi .k{font-size:32px;font-weight:300;color:#2B2F36;letter-spacing:-.5px}
.kpi .l{font-size:13.5px;color:#6B7280;margin-bottom:6px}
.delta{font-size:12.5px;color:#16A34A;font-weight:600}
.delta.grey{color:#8A90A0;font-weight:500}
.heroStats.wide{grid-template-columns:repeat(4,1fr);gap:16px}
.hstat{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.28);border-radius:12px;padding:13px 15px}
.hstat .v{font-size:26px;font-weight:700;letter-spacing:-.5px}
.hstat .s{font-size:11.5px;color:rgba(255,255,255,.75);margin-top:3px}
.ringbox{display:flex;align-items:center;justify-content:center;flex:0 0 auto}
@media(max-width:1150px){.heroStats.wide{grid-template-columns:repeat(2,1fr)}}
.heroRow{display:flex;gap:26px;align-items:center;flex-wrap:wrap}
.heroStats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;flex:1;min-width:280px}
.hstat .v{font-size:23px;font-weight:700}
.hstat .t{font-size:12.5px;color:rgba(255,255,255,.85);display:flex;align-items:center;gap:6px}
.dot{width:8px;height:8px;border-radius:50%;background:#fff;display:inline-block}
.dot2{width:8px;height:8px;border-radius:50%;display:inline-block}
.barchart{display:flex;align-items:flex-end;gap:12px;height:200px;padding-top:24px;overflow-x:auto}
.bcol{flex:1;min-width:56px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.bbar{width:100%;border-radius:6px 6px 0 0}
.bval{font-size:11.5px;font-weight:700;color:#2A60FF;margin-bottom:5px}
.blab{font-size:11px;color:#8A90A0;margin-top:7px;text-align:center;line-height:1.25;height:auto;max-height:46px;word-break:break-word;hyphens:auto}
.hrow{display:grid;grid-template-columns:170px 1fr 74px;align-items:center;gap:10px;margin:8px 0}
.hlab{font-size:12.5px;color:#4B5563}
.htrack{background:#EEF0F4;height:14px;border-radius:7px;overflow:hidden}
.hfill{height:100%;background:#2A60FF;border-radius:7px}
.hval{font-size:12.5px;color:#6B7280;text-align:right;font-variant-numeric:tabular-nums}
.catrow{display:grid;grid-template-columns:1fr auto;gap:6px;margin-bottom:4px;font-size:13px}
.catrow .c1{display:flex;align-items:center;gap:8px;color:#4B5563}
.catrow .c2{font-weight:700;font-variant-numeric:tabular-nums}
.catbar{grid-column:1/-1;height:7px;background:#EEF0F4;border-radius:4px;overflow:hidden;margin-bottom:14px}
.catbar div{height:100%;background:#2A60FF;border-radius:4px}
.miniRow{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
.mini{background:#fff;border:1px solid #E4E8F0;border-radius:12px;padding:13px 15px;font-size:12.5px;color:#6B7280}
.mini span{display:block;font-size:16px;font-weight:700;color:#2B2F36;margin-bottom:3px}
.avail{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.avail .ok,.avail .no{border-radius:10px;padding:16px 18px;font-size:13px}
.avail .ok{background:#F0FDF4;border:1px solid #DCFCE7}
.avail .no{background:#FFF7ED;border:1px solid #FFEDD5}
.avail b{display:block;margin-bottom:8px;font-size:13.5px}
.avail .ok b{color:#16A34A}.avail .no b{color:#C2410C}
.avail ul{margin:0;padding-left:18px;color:#4B5563}
.avail li{margin:5px 0}
.bul{margin:0;padding-left:18px;font-size:13.2px;color:#4B5563}
.bul li{margin:9px 0;line-height:1.55}
.steps{margin:0;padding-left:20px;font-size:13.2px;color:#4B5563}
.steps li{margin:10px 0;line-height:1.55}
.tagwrap{display:flex;flex-wrap:wrap;gap:8px}
.tag{background:#E7EDFF;color:#2A60FF;font-size:12.5px;font-weight:600;padding:5px 11px;border-radius:999px}
.adgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}
.adcard{border:1px solid #E9ECF2;border-radius:12px;overflow:hidden;background:#fff;box-shadow:0 1px 6px rgba(16,24,40,.05)}
.adimg{position:relative;display:block;line-height:0}
.adimg img{width:100%;height:172px;object-fit:cover;background:#EEF0F4;display:block}
.adfmt{position:absolute;left:10px;top:10px;background:rgba(42,96,255,.92);color:#fff;font-size:10.5px;font-weight:700;padding:3px 9px;border-radius:999px;text-transform:uppercase;letter-spacing:.4px}
.adbody{padding:14px 16px 16px}
.adbrand{font-weight:700;font-size:13.5px;color:#2B2F36;margin-bottom:6px}
.adbrand span{color:#8A90A0;font-weight:500}
.adlabel{font-size:10.5px;letter-spacing:.7px;font-weight:700;color:#2A60FF;margin:11px 0 4px}
.adhook{font-size:14px;font-weight:600;color:#2B2F36;line-height:1.4}
.adwhy{font-size:12.5px;color:#4B5563;line-height:1.55}
.admeta{font-size:11px;color:#8A90A0;margin-top:10px;line-height:1.5}
.adlink{font-size:12px;font-weight:600;display:inline-block;margin-top:8px}
.postlink{font-size:12px;font-weight:600;white-space:nowrap}
.tabs{display:flex;gap:8px;margin:0 0 4px;flex-wrap:wrap}
.tab{background:#F1F3F7;border:1px solid #E6E9EF;color:#6B7280;padding:8px 15px;border-radius:9px;cursor:pointer;font-size:13px;font-weight:600}
.tab.on{background:#2A60FF;border-color:#2A60FF;color:#fff}
table{width:100%;border-collapse:collapse;font-size:13px}
table.compact td{padding:8px 6px}
th,td{padding:10px 9px;text-align:left;border-bottom:1px solid #EEF0F4;vertical-align:middle}
th{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#8A90A0;font-weight:600;background:#FAFBFC}
tr:hover td{background:#FAFBFF}
.num{text-align:right;font-variant-numeric:tabular-nums}
.strong{font-weight:700;color:#2B2F36}
.sub2{font-size:11.5px;color:#8A90A0}
.cap{color:#4B5563;font-size:12.5px;max-width:380px}
.pill2{display:inline-block;background:#E7EDFF;color:#2A60FF;font-size:11px;padding:3px 9px;border-radius:999px;font-weight:600;white-space:nowrap}
.th{width:46px;height:46px;object-fit:cover;border-radius:7px;background:#EEF0F4;display:block}
a{color:#2A60FF;text-decoration:none}
a:hover{text-decoration:underline}
.footer{margin-top:26px;font-size:12px;color:#8A90A0;line-height:1.7;background:#fff;border:1px solid #E4E8F0;border-radius:14px;padding:18px 22px}
@media(max-width:1250px){.grid{grid-template-columns:repeat(2,1fr)}.span6,.span4,.span3,.span2{grid-column:span 2}.avail{grid-template-columns:1fr}.side{display:none}}
@media(max-width:760px){.grid{grid-template-columns:1fr}.span6,.span4,.span3,.span2{grid-column:span 1}.hrow{grid-template-columns:120px 1fr 62px}}
"""


JS = """
function sec(id, el){
  document.querySelectorAll('.sec').forEach(s=>s.style.display='none');
  document.getElementById(id).style.display='block';
  document.querySelectorAll('.tab2,.sic').forEach(t=>t.classList.remove('on'));
  if(el) el.classList.add('on');
  const idx = ['s1','s2','s3','s4','s5'].indexOf(id);
  const items = document.querySelectorAll('.tab2');
  if(idx>=0 && items[idx]) items[idx].classList.add('on');
  const sic = document.querySelectorAll('.sic');
  if(idx>=0 && sic[idx]) sic[idx].classList.add('on');
  window.scrollTo(0,0);
}
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

html_doc = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EDEKA · Social Media &amp; Marketing Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><div class="app">
  <div class="main">
    <header class="top">
      <h1>Edeka <span>Social Media &amp; Marketing Intelligence</span></h1>
      <div class="tabs2">
        <span class="tab2 on" onclick="sec('s1',this)">01 Overview</span>
        <span class="tab2" onclick="sec('s2',this)">02 Profiles &amp; Content</span>
        <span class="tab2" onclick="sec('s3',this)">03 Campaign Impact</span>
        <span class="tab2" onclick="sec('s4',this)">04 Competitor Intelligence</span>
        <span class="tab2" onclick="sec('s5',this)">05 Insights</span>
      </div>
      <div class="spacer"></div>
      <span class="meta">Datenstand {STAND} · {de(N_KONTEN)} Profile · {de(N_POSTS)} Beiträge</span>
      <div class="avatar">GL</div>
    </header>

    <!-- 01 OVERVIEW -->
    <div id="s1" class="sec">
      <div class="grid">
        <div class="card blue span6">
          <span class="arrow">↗</span>
          <h3 style="font-size:20px">01 · Overview — Gesamtüberblick</h3>
          <p class="hint">Hochlevel-Kennzahlen über alle erfassten Instagram-Profile · Datenstand {STAND}</p>
          <div class="heroRow">
            <div class="heroStats wide">
              <div class="hstat"><div class="v">{de(N_KONTEN)}</div><div class="t"><span class="dot"></span>Instagram-Profile</div><div class="s">von 222 erfassten Konten</div></div>
              <div class="hstat"><div class="v">{de(N_FOLLOWER)}</div><div class="t"><span class="dot"></span>Follower gesamt</div><div class="s">über alle Profile</div></div>
              <div class="hstat"><div class="v">{de(OER_MED, 2)} %</div><div class="t"><span class="dot"></span>Median-ER</div><div class="s">Mittelwert {de(OER, 1)} % · ab 500 Followern</div></div>
              <div class="hstat"><div class="v">{de(N_POSTS)}</div><div class="t"><span class="dot"></span>Analysierte Beiträge</div><div class="s">je Konto die letzten 12 Beiträge</div></div>
              <div class="hstat"><div class="v">{de(O_INT_POST)}</div><div class="t"><span class="dot"></span>Ø Interaktionen je Beitrag</div><div class="s">Likes + Kommentare</div></div>
              <div class="hstat"><div class="v">{N_AKTIV30}</div><div class="t"><span class="dot"></span>Aktive Profile (30 Tage)</div><div class="s">{PCT_AKTIV:.0f} % aller Profile</div></div>
              <div class="hstat"><div class="v">{de(mov_med[0]['er_med'], 1)} %</div><div class="t"><span class="dot"></span>Beste Median-ER</div><div class="s">@{esc(mov_med[0]['handle'])} · {mov_med[0]['n_valid']} Beiträge</div></div>
              <div class="hstat"><div class="v">3</div><div class="t"><span class="dot"></span>Nationale Marken-Accounts</div><div class="s">@edeka · @edekakarriere · @dein.edeka</div></div>
            </div>
            <div class="ringbox">{ring(PCT_AKTIV)}</div>
          </div>
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>{'Interaktionen je Beitrag nach Woche' if USE_NORM else 'Leistungsverlauf · 12 Wochen'}</h3>
          <p class="hint">{('Likes + Kommentare je Beitrag, normalisiert. Keine der 12 Wochen ist für alle {1} Konten vollständig abgedeckt (je Konto nur die letzten 12 Beiträge, vollständig erst ab {2}), deshalb keine absoluten Volumenwerte, die zwischen den Wochen vergleichbar wären.'.format(FULL_WEEKS, de(N_KONTEN), COVER_START.strftime('%d.%m.%Y')) if FULL_WEEKS == 0 else 'Likes + Kommentare je Beitrag, normalisiert. {0} der 12 Wochen sind für alle {1} Konten vollständig abgedeckt (vollständig ab {2}), deshalb ohne absolute Volumenwerte.'.format(FULL_WEEKS, de(N_KONTEN), COVER_START.strftime('%d.%m.%Y'))) if USE_NORM else 'Interaktionen (Likes + Kommentare) je Woche über alle Profile'}</p>
          {svg_line(wk_ipost if USE_NORM else wk_int, wk_lab)}
          <p class="hint" style="margin:10px 0 0">{'Peak {0} Interaktionen je Beitrag · aktuelle Woche {1} · {2} Beiträge'.format(f"{max(wk_ipost):,.0f}".replace(',', '.'), f"{wk_ipost[-1]:,.0f}".replace(',', '.'), de(wk_cnt[-1])) if USE_NORM else 'Peak {0} Interaktionen · aktuelle Woche {1} · {2} Beiträge'.format(de(max(wk_int)), de(wk_int[-1]), de(wk_cnt[-1]))}</p>
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
      <div class="grid">
        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>02 · Profiles &amp; Content — Analyse je Profil</h3>
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
            <table><thead><tr><th>#</th><th>Media</th><th>Profil</th><th>Text</th><th class="num">Likes</th><th class="num">Komment.</th><th class="num">Datum</th><th>Format</th><th>Link</th></tr></thead>
            <tbody>{t_best()}</tbody></table>
          </div>
          <div id="u3" class="panel" style="display:none">
            <table><thead><tr><th>#</th><th>Media</th><th>Profil</th><th>Text</th><th class="num">Likes</th><th class="num">Komment.</th><th class="num">Datum</th><th>Format</th><th>Link</th></tr></thead>
            <tbody>{t_worst()}</tbody></table>
            <p class="hint" style="margin-top:10px">Nur Beiträge mit Like-Wert aus Profilen ab 500 Followern. {de(N_NO_LIKES)} Beiträge ohne Like-Wert (0 oder 1 Like, vom Anbieter nicht geliefert) sind in ER, Rankings und Empfehlungen ausgeblendet.</p>
          </div>
          <div id="u4" class="panel" style="display:none">
            <table><thead><tr><th>#</th><th>Profil</th><th class="num">Beiträge 30 T.</th><th class="num">Beiträge ges.</th><th class="num">Interaktionen</th><th class="num">Follower</th></tr></thead>
            <tbody>{t_aktiv()}</tbody></table>
          </div>
        </div>

        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>Leistung nach Format</h3>
          <p class="hint">Ø Engagement-Rate je Format — Median daneben, weil einzelne Viral-Beiträge den Mittelwert verzerren</p>
          <div class="grid" style="gap:14px">{fmt_cards}</div>
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Beste Wochentage</h3>
          <p class="hint">Median-ER je Tag (Beiträge mit Follower-Daten)</p>
          {bars_h(WD_ROWS, 'label', 'med', lambda v: de(v, 2) + ' %', 7)}
        </div>

        <div class="card span3">
          <span class="arrow">↗</span>
          <h3>Beste Uhrzeiten</h3>
          <p class="hint">Median-ER je Stunde (min. 40 Beiträge)</p>
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
      <div class="grid">
        <div class="card blue span6">
          <span class="arrow">↗</span>
          <h3 style="font-size:20px">03 · Campaign Impact — Wirkung der Kampagnen</h3>
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
      </div>
    </div>

    <!-- 04 COMPETITOR -->
    <div id="s4" class="sec" style="display:none">
      <div class="grid">
        <div class="card span6">
          <span class="arrow">↗</span>
          <h3>04 · Competitor Intelligence — Wettbewerbsanalyse</h3>
          <p class="hint">Laufende Werbeanzeigen aus der Meta Ads Library (Deutschland, aktiv), abgefragt am {STAND_ADS}</p>
          <table><thead><tr><th>Marke</th><th class="num">Anzeigen im Sample / Treffer</th><th>Werbeanzeigen-Seiten</th>
            <th>Formate</th><th>CTA-Typen</th><th>Beispiel-Nachrichten</th><th class="num">Neuester Start</th></tr></thead>
            <tbody>{t_ads()}</tbody></table>
          <p class="hint" style="margin-top:10px">Die Ad Library zeigt max. 20 Treffer je Abfrage — die Zahlen sind eine Untergrenze, kein Gesamtbestand. Ausgewertet wurden nur Anzeigen der eigenen Marken-Seiten (fremde Treffer wie Rabatt-Apps verwässern die Suche).</p>
        </div>

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
          <table class="compact"><tbody>
            {FRAME_ROWS}
          </tbody></table>
          <p class="hint" style="margin-top:10px"><b>Einschränkung:</b> Die Meta Ads Library zeigt nur öffentliche Anzeigen (Seite, Laufzeit, Format, Text). Sie liefert <b>keine</b> Reichweiten-, Kosten- oder Performance-Werte der Konkurrenz.</p>
        </div>
      </div>
    </div>

    <!-- 05 INSIGHTS -->
    <div id="s5" class="sec" style="display:none">
      <div class="grid">
        <div class="card blue span6">
          <span class="arrow">↗</span>
          <h3 style="font-size:20px">05 · Insights &amp; Recommendations — Erkenntnisse &amp; Empfehlungen</h3>
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
            <li><b>Themen mit Zug:</b> {', '.join('#' + t for t, c in TOP_TAGS[:5])} — Angebote, Regionales und Humor (Azubi-/Kassen-Sketche) erzeugen die meisten Kommentare.</li>
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

    <div class="footer">
      <b>Methodik:</b> Engagement-Rate = (Likes + Kommentare) ÷ Follower × 100, gemittelt über die letzten 12 Beiträge je Profil;
      Profile ab 500 Followern und mindestens 5 Beiträgen im Ranking. Median zusätzlich zum Mittelwert, weil einzelne Viral-Beiträge verzerren.
      Aktivität = Beiträge in den letzten 30 Tagen (Datenstand {STAND}). Uhrzeiten in {TZ_LABEL} (deutsche Ortszeit, aus UTC umgerechnet).
      Wettbewerbsdaten: Meta Ads Library, Deutschland, Status „aktiv", Abfrage {STAND_ADS}, max. 20 Treffer je Marke.
      Quellen: Instagram-Profil- und Beitragsdaten, öffentlich · Census: {de(N_KONTEN)} berücksichtigte Profile von {de(N_GES)} erfassten Konten.
      Reichweite, Impressionen, Kampagnen- und App-Daten sind nicht Teil dieser Auswertung (siehe 03).
      Datenaufbereitung: {de(N_AUSGESCHLOSSEN)} Konten ausgeschlossen (nicht in Deutschland bzw. kein EDEKA-Markt, siehe data/excluded_accounts.csv), {de(N_FREMDE_POSTS)} Beiträge fremder Owner entfernt (owner weder das Profil noch der EDEKA-Verbund), {de(N_NO_LIKES)} Beiträge ohne Like-Wert für ER- und Ranking-Auswertungen ausgeblendet ({de(N_POSTS_GUELTIG)} von {de(N_POSTS)} Beiträgen mit Like-Wert).
    </div>
  </div>
</div>
<script>{JS}</script>
</body></html>"""


# ---------------- v2-Layout (unveraendert vom Stand auf main) ----------------
V2_CSS = """
/* --- v2 tweaks --- */
.meta{font-size:11px;color:#9AA0AE;letter-spacing:.1px}
.card{min-width:0}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px}
.tw table{min-width:640px}
.chartw{overflow-x:auto}
@media(max-width:760px){.chartw svg{min-width:560px}}
/* hero stats: no boxes, separated by thin lines */
.heroStats{gap:0!important;overflow:hidden;min-width:0}
.heroStats .hstat{background:none;border:0;border-radius:0;border-left:1px solid rgba(255,255,255,.28);border-top:1px solid rgba(255,255,255,.28);margin:-1px 0 0 -1px;padding:16px 20px}
.heroRow{display:block}
@media(max-width:760px){
  .main{padding:0 14px 36px}
  .top{display:block;padding:14px 0 10px}
  .top h1{font-size:15px;margin-bottom:8px}
  .tabs2{margin:0 -14px;padding:0 14px 4px;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}
  .tabs2::-webkit-scrollbar{display:none}
  .meta{display:block;margin-top:6px}
  .card{padding:18px}
  .card h3{padding-right:26px}
  .card h3[style]{font-size:17px!important}
  .miniRow{grid-template-columns:1fr 1fr;gap:10px}
  .mini span{font-size:14px;word-break:break-word}
  .tw table{min-width:760px}
  .heroStats,.heroStats.wide{grid-template-columns:repeat(2,1fr)!important}
  .heroStats .hstat{padding:14px 12px}
  .hstat .v{font-size:21px}
  .hstat .t{font-size:12px;align-items:flex-start}
  .hstat .t .dot{margin-top:5px;flex:0 0 auto}
  .hstat .s{font-size:11px;word-break:break-word}
  .tabs{flex-wrap:nowrap;overflow-x:auto}
  .tab{white-space:nowrap}
  .adgrid{grid-template-columns:1fr}
  .footer{padding:16px}
}
"""
html_doc = html_doc.replace('</style>', V2_CSS + '</style>', 1)
html_doc = re.sub(r'\s*<div class="avatar">GL</div>', '', html_doc)
html_doc = re.sub(r'\n[ \t]*<div class="ringbox">.*?</svg></div>', '', html_doc, flags=re.S)
html_doc = html_doc.replace(
    '<svg viewBox="0 0 760 210" width="100%" height="210" preserveAspectRatio="none">',
    '<div class="chartw"><svg viewBox="0 0 760 210" width="100%" style="height:auto;display:block">')
html_doc = re.sub(r'(<text x="[\d.]+" y="17\.0" font-size="11" font-weight="700" fill="#2A60FF" text-anchor=")middle(">)',
                  r'\g<1>end\2', html_doc)
assert html_doc.count('</svg>') == 1, html_doc.count('</svg>')
html_doc = html_doc.replace('</svg>', '</svg></div>', 1)
assert html_doc.count('<table') == html_doc.count('</table>')
html_doc = html_doc.replace('<table', '<div class="tw"><table')
html_doc = html_doc.replace('</table>', '</table></div>')

open(os.path.join(SITE, 'index.html'), 'w').write(html_doc + '\n')
print("HTML:", os.path.join(SITE, 'index.html'), len(html_doc), "bytes")
print(f"Profile={N_KONTEN} Follower={N_FOLLOWER} Beiträge={N_POSTS} aktiv30={N_AKTIV30} ØER={OER:.1f}%")
print("Format-Reihenfolge:", [(r['label'], round(r['er'], 1), round(r['er_med'], 2)) for r in fmt_rows])
print("Bilder:", len(os.listdir(IMG)))
