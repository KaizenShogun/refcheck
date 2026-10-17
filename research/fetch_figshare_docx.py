#!/usr/bin/env python3
"""Freeze a corpus of REAL Word documents deposited on Figshare.

Zenodo's Word deposits turned out to be mostly "flattened": on 2026-10-17 only
2 of 90 kept their reference manager's citation fields. Theses and manuscripts
in Figshare's institutional repositories are more often the author's working
file, fields and all. Same rules as fetch_ris_corpus.py: public records only
(everything public on Figshare carries a licence), files under --max-bytes,
one request at a time with a pause, and a manifest with sha256 so the
measurement can be repeated on the same bytes.

    python3 -I research/fetch_figshare_docx.py --out DIR --q "thesis"

MIT. No key, no third-party dependency.
"""
import argparse
import hashlib
import json
import os
import time
import urllib.request

AGENTE = "refcheck-research/1.0 (https://github.com/KaizenShogun/refcheck)"
API = "https://api.figshare.com/v2"


def pide(url, pausa, cuerpo=None):
    time.sleep(pausa)
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE,
                                               "Content-Type": "application/json"},
                                 data=json.dumps(cuerpo).encode() if cuerpo else None)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--q", default="")
    p.add_argument("--paginas", type=int, default=5)
    p.add_argument("--limite", type=int, default=100)
    p.add_argument("--max-bytes", type=int, default=5_000_000)
    p.add_argument("--pausa", type=float, default=0.7)
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ruta = os.path.join(a.out, "manifest.json")
    manifiesto = json.load(open(ruta)) if os.path.exists(ruta) else []
    hechos = {m["figshare_id"] for m in manifiesto}
    for pagina in range(1, a.paginas + 1):
        q = ":extension: docx" + (f" AND {a.q}" if a.q else "")
        try:
            arts = json.loads(pide(f"{API}/articles/search", a.pausa,
                                   {"search_for": q, "page": pagina, "page_size": 50}))
        except Exception as e:
            print(f"  ! búsqueda p{pagina}: {e}", flush=True)
            break
        if not arts:
            break
        for art in arts:
            if len(manifiesto) >= a.limite:
                break
            if art["id"] in hechos:
                continue
            hechos.add(art["id"])
            try:
                ficha = json.loads(pide(f"{API}/articles/{art['id']}", a.pausa))
            except Exception as e:
                print(f"  ! {art['id']}: {e}", flush=True)
                continue
            for fi in ficha.get("files") or []:
                nombre = fi.get("name") or ""
                if not nombre.lower().endswith(".docx") or not 0 < (fi.get("size") or 0) <= a.max_bytes:
                    continue
                try:
                    crudo = pide(fi["download_url"], a.pausa)
                except Exception as e:
                    print(f"  ! {art['id']} {nombre}: {e}", flush=True)
                    continue
                local = f"fs{art['id']}_{len(manifiesto):03d}.docx"
                with open(os.path.join(a.out, local), "wb") as f:
                    f.write(crudo)
                manifiesto.append(dict(
                    fichero=local, figshare_id=art["id"], titulo=(ficha.get("title") or "")[:200],
                    tipo=ficha.get("defined_type_name"), nombre_original=nombre,
                    doi=ficha.get("doi", ""), licencia=(ficha.get("license") or {}).get("name", ""),
                    bytes=len(crudo), sha256=hashlib.sha256(crudo).hexdigest(),
                    url=fi["download_url"]))
                print(f"  + {local} {len(crudo):>9,} B {nombre[:50]}", flush=True)
                break  # one file per deposit
        with open(ruta, "w") as f:
            json.dump(manifiesto, f, indent=1)
    print(f"{len(manifiesto)} ficheros -> {ruta}", flush=True)


if __name__ == "__main__":
    main()
