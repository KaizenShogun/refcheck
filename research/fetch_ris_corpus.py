#!/usr/bin/env python3
"""Freeze a corpus of REAL .ris files — the ones people doing reviews deposit.

refcheck reads a `.ris` through the forgiving loose-text path, and a comment in
refcheck.py has claimed since the start that there "its DOIs are found perfectly
well". That was never measured. It is the same assumption that turned out to be
a trap for `.nbib` on 2026-09-12, where a record format read as loose text
returned OTHER people's papers.

So this fetches .ris files that real people exported from Scopus, Web of Science,
Google Scholar and Publish or Perish and deposited on Zenodo alongside their
systematic reviews. Not files I wrote to be kind to myself.

Frozen on disk with a manifest (record id, licence, URL, sha256) because a
measurement that cannot be repeated on the same bytes cannot tell a code change
from a corpus change — the lesson of 2026-09-18, when I published a comparison
between two different samples and called it an improvement.

    python3 research/fetch_ris_corpus.py --out ris_corpus/

Only open-access records are downloaded, and only files under --max-bytes.
Zenodo is a free public service: one request at a time, with a pause.

MIT. No key, no third-party dependency.
"""
import argparse
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

AGENTE = "refcheck-research/1.0 (https://github.com/KaizenShogun/refcheck)"
BUSQUEDA = "https://zenodo.org/api/records"


def pide(url, pausa):
    time.sleep(pausa)
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def busca(paginas, por_pagina, pausa):
    """Zenodo records whose files include a .ris, newest first."""
    vistos = []
    for pagina in range(1, paginas + 1):
        q = urllib.parse.urlencode(
            {"q": "filetype:ris", "size": por_pagina, "page": pagina}
        )
        datos = json.loads(pide(f"{BUSQUEDA}?{q}", pausa))
        hits = datos.get("hits", {}).get("hits", [])
        if not hits:
            break
        vistos.extend(hits)
    return vistos


def descarga(registros, destino, max_bytes, limite, pausa):
    os.makedirs(destino, exist_ok=True)
    manifiesto = []
    for reg in registros:
        if len(manifiesto) >= limite:
            break
        meta = reg.get("metadata", {})
        # Only what the depositor made open. A restricted record is not mine to
        # pull, and a measurement does not need it.
        if reg.get("access", {}).get("files") != "open" and meta.get(
            "access_right"
        ) not in (None, "open"):
            continue
        for fichero in reg.get("files") or []:
            clave = fichero.get("key") or ""
            if not clave.lower().endswith(".ris"):
                continue
            tam = fichero.get("size") or 0
            if tam > max_bytes or tam == 0:
                continue
            enlace = (fichero.get("links") or {}).get("self")
            if not enlace:
                continue
            try:
                crudo = pide(enlace, pausa)
            except Exception as e:  # a missing file is a fact, not a crash
                print(f"  ! {reg['id']} {clave}: {e}")
                continue
            nombre = f"{reg['id']}_{len(manifiesto):03d}.ris"
            with open(os.path.join(destino, nombre), "wb") as f:
                f.write(crudo)
            lic = meta.get("license") or {}
            manifiesto.append(
                {
                    "fichero": nombre,
                    "zenodo_id": reg["id"],
                    "titulo": (meta.get("title") or "")[:200],
                    "nombre_original": clave,
                    "doi": meta.get("doi", ""),
                    "licencia": lic.get("id") or lic.get("$ref") or "",
                    "bytes": len(crudo),
                    "sha256": hashlib.sha256(crudo).hexdigest(),
                    "url": enlace,
                }
            )
            print(f"  + {nombre}  {len(crudo):>9,} B  {clave[:50]}")
            break  # one file per deposit: 20 exports of one review is one habit
    return manifiesto


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="ris_corpus")
    p.add_argument("--paginas", type=int, default=6)
    p.add_argument("--por-pagina", type=int, default=25)
    p.add_argument("--limite", type=int, default=40)
    p.add_argument("--max-bytes", type=int, default=4_000_000)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args()

    registros = busca(a.paginas, a.por_pagina, a.pausa)
    print(f"{len(registros)} Zenodo records with a .ris among their files")
    manifiesto = descarga(registros, a.out, a.max_bytes, a.limite, a.pausa)
    ruta = os.path.join(a.out, "manifest.json")
    with open(ruta, "w") as f:
        json.dump(manifiesto, f, indent=1)
    total = sum(m["bytes"] for m in manifiesto)
    print(f"\n{len(manifiesto)} files, {total:,} bytes -> {ruta}")


if __name__ == "__main__":
    main()
