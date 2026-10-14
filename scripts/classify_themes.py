#!/usr/bin/env python3
"""Captions der EDEKA-Beitraege per LLM einer Themenkategorie zuordnen.

Aufruf:  python3 scripts/classify_themes.py
Ausgabe: data/themes.json   [{id, thema, confidence}, ...]

Basis: data/posts_raw.json (eine Zeile je Profil-Beitrag, id = Post-URL).
Modell: openai/gpt-4o-mini ueber orcarouter (Schluessel in CREDENTIALS_MASTER.env).
"""
import json, os, subprocess, sys, concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
RAW = os.path.join(DATA, 'posts_raw.json')
OUT = os.path.join(DATA, 'themes.json')
MODEL = 'openai/gpt-4o-mini'
BATCH = 30

KATEGORIEN = ["Angebot/Preis", "Rezept/Food", "Humor/Team/Azubi", "Region/Lieferant",
              "Recruiting/Karriere", "Gewinnspiel", "Event/Aktion", "Sonstiges"]

PROMPT = """Du ordnest Instagram-Captions deutscher EDEKA-Supermarkt-Konten EINER Kategorie zu.
Kategorien: Angebot/Preis (Prospekte, Rabatte, Preise, Aktionen), Rezept/Food (Rezepte, Gerichte,
Produktvorstellungen zum Essen), Humor/Team/Azubi (Sketche, Witze, Mitarbeitende, Auszubildende),
Region/Lieferant (Regionen, lokale Erzeuger, Zusammenarbeit vor Ort), Recruiting/Karriere
(Stellenanzeigen, Bewerbung, Ausbildung), Gewinnspiel (Gewinn, verlosen, Mitmachen),
Event/Aktion (Filialeröffnung, Messen, Kampagnen wie LEGO, Gedenktage), Sonstiges (alles andere).
Antworte AUSSCHLIESSLICH mit einem JSON-Array, ohne Markdown:
[{"id":"<post-id>","thema":"<Kategorie>","confidence":<0.0-1.0>}]"""


def api_key():
    path = os.path.expanduser('~/.hermes/CREDENTIALS_MASTER.env')
    for line in open(path):
        if line.startswith('ORCAROUTER_API_KEY='):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise SystemExit('ORCAROUTER_API_KEY fehlt')


KEY = api_key()


def call(batch):
    items = [{'id': i, 'text': (t or '')[:400]} for i, t in batch]
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": PROMPT},
                     {"role": "user", "content": json.dumps(items, ensure_ascii=False)}],
        "temperature": 0,
    })
    for _ in range(3):
        p = subprocess.run(["curl", "-s", "-m", "90", "https://api.orcarouter.ai/v1/chat/completions",
                            "-H", f"Authorization: Bearer {KEY}",
                            "-H", "Content-Type: application/json", "-d", payload],
                           capture_output=True, text=True, timeout=100)
        try:
            content = json.loads(p.stdout)['choices'][0]['message']['content']
        except Exception:
            continue
        content = content.strip()
        if content.startswith('```'):
            content = content.strip('`').lstrip('json').strip()
        try:
            rows = json.loads(content)
            out = []
            for r in rows:
                th = str(r.get('thema', '')).strip()
                if th not in KATEGORIEN:
                    th = 'Sonstiges'
                out.append({'id': r.get('id'), 'thema': th,
                            'confidence': float(r.get('confidence', 0.5))})
            if out:
                return out
        except Exception:
            continue
    return []


def main():
    beitraege = []
    for rec in json.load(open(RAW)):
        h = rec['handle']
        for p in rec.get('posts') or []:
            if p.get('url'):
                beitraege.append((p['url'], p.get('caption') or ''))
    exist = {}
    if os.path.exists(OUT):
        exist = {r['id']: r for r in json.load(open(OUT))}
    todo = [(u, c) for u, c in beitraege if u not in exist]
    print(f"Beitraege: {len(beitraege)} · bereits vorhanden: {len(exist)} · zu klassifizieren: {len(todo)}")
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    neu, leer = [], 0
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for i, res in enumerate(ex.map(call, batches), 1):
            if res:
                neu.extend(res)
            else:
                leer += 1
            if i % 10 == 0:
                print(f"  {i}/{len(batches)} Batches, {len(neu)} Klassifizierungen", flush=True)
    alle = list(exist.values()) + neu
    seen, final = set(), []
    for r in alle:
        if r['id'] and r['id'] not in seen:
            seen.add(r['id'])
            final.append(r)
    json.dump(final, open(OUT, 'w'), ensure_ascii=False, indent=1)
    print(f"geschrieben: {len(final)} Klassifizierungen -> {OUT} · leere Batches: {leer}")


if __name__ == '__main__':
    main()
