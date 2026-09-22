#!/usr/bin/env python3
"""What happens when a watch file meets the wrong bibliography — measured.

refcheck's watch state (--watch in the CLI, the saved .json on the page) is
deliberately never pruned: someone who points it at the wrong file once must not
lose the only baseline they have. The cost of that choice was written down on
2026-09-21 as a guess: "someone watching two bibliographies can clobber one with
the other and nothing tells them". A guess is not a reason to build a guard, so
this measures it.

What it can measure, and what it cannot: I have no users, so I cannot measure how
OFTEN a mix-up happens. What is measurable, on real references and with the real
code, is what the tool DOES when it happens, and whether any signal separates a
mix-up from a bibliography that legitimately changed between runs. That second
half is the one that decides the design — a warning that fires on the ordinary
case of "I added forty papers this month" would be worse than no warning at all.

Input is a --json run of refcheck over a real bibliography, so every verdict here
is a real answer from Crossref and PubMed and no scenario invents a notice:

    python3 refcheck.py big.nbib --json > res.json
    python3 research/measure_watch_mixup.py res.json

MIT. No key, no network, no third-party dependency.
"""
import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The real code, imported and not copied: a private reimplementation here would
# let these numbers describe bookkeeping that no longer exists.
import refcheck


def estado_de(resultados, ahora=1.0):
    return refcheck.actualiza_vigilancia(None, copy.deepcopy(resultados), ahora=ahora)


def claves(resultados):
    return {k for k in (refcheck.clave_vigilada(r) for r in resultados) if k}


def mide(nombre, base, corre, legitimo):
    """One scenario: a state built from `base`, then a run over `corre`."""
    estado = estado_de(base)
    cambios = refcheck.compara_vigilancia(estado, copy.deepcopy(corre))
    despues = refcheck.actualiza_vigilancia(copy.deepcopy(estado),
                                            copy.deepcopy(corre), ahora=2.0)
    vigiladas = set(estado["vistas"])
    del_fichero = claves(corre)
    solapa = vigiladas & del_fichero
    # The candidate signal. Asymmetric on purpose: "how much of what I am
    # watching does this file still contain" stays at 1.0 when a bibliography
    # GROWS, which is the common legitimate change and the one a symmetric
    # measure would flag.
    cobertura = len(solapa) / len(vigiladas) if vigiladas else 1.0
    nuevas_marcadas = sum(1 for r in cambios["nuevas"] if r["avisos"])
    return {
        "escenario": nombre,
        "legitimo": legitimo,
        "vigiladas": len(vigiladas),
        "en_fichero": len(del_fichero),
        "solapan": len(solapa),
        "cobertura_del_estado": round(cobertura, 4),
        "nuevos_avisos": len(cambios["nuevos"]),
        "ausentes": len(cambios["ausentes"]),
        "no_comprobados": len(cambios["no_comprobados"]),
        "nuevas_en_el_fichero": len(cambios["nuevas"]),
        "de_ellas_ya_con_aviso": nuevas_marcadas,
        "estado_despues": len(despues["vistas"]),
        "crecimiento": len(despues["vistas"]) - len(vigiladas),
    }


def escenarios(res):
    """Six ways a watch file can meet a bibliography, five of them innocent.

    Built by slicing ONE real bibliography, so the references, the DOIs and the
    verdicts are real; what is simulated is only which of them a given run sees.
    """
    n = len(res)
    m = n // 2
    return [
        # The ordinary case: same file, run again a month later.
        ("igual", res, res, True),
        # A review that grew: last month's state, this month's longer file.
        ("creció 25%", res[:int(n * .8)], res, True),
        # A file that shrank: someone dropped a fifth of the references.
        ("encogió 20%", res, res[:int(n * .8)], True),
        # A review genuinely rewritten between runs: half the references changed.
        ("medio reescrito", res[:int(n * .6)], res[int(n * .3):int(n * .9)], True),
        # Almost nothing left: the hardest legitimate case to tell from a mix-up.
        ("reescrito casi entero", res[:m], res[m - int(n * .05):], True),
        # The mix-up: two bibliographies with nothing in common, one watch file.
        ("fichero equivocado", res[:m], res[m:], False),
    ]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("resultados", help="output of refcheck.py --json over a real file")
    p.add_argument("--json", metavar="FILE", help="write the table as JSON too")
    a = p.parse_args()

    with open(a.resultados, encoding="utf-8") as f:
        res = json.load(f)
    # Only watchable references matter here; the rest never enter a state file.
    res = [r for r in res if refcheck.clave_vigilada(r)]
    print("%d watchable references, %d of them carrying a notice\n"
          % (len(res), sum(1 for r in res if r["avisos"])))

    filas = [mide(*e) for e in escenarios(res)]

    cab = ("scenario", "legit", "watched", "overlap", "coverage",
           "new refs", "…flagged", "state after")
    print("%-22s %-5s %8s %8s %9s %9s %9s %12s" % cab)
    for f in filas:
        print("%-22s %-5s %8d %8d %8.1f%% %9d %9d %12d"
              % (f["escenario"], "yes" if f["legitimo"] else "NO",
                 f["vigiladas"], f["solapan"], 100 * f["cobertura_del_estado"],
                 f["nuevas_en_el_fichero"], f["de_ellas_ya_con_aviso"],
                 f["estado_despues"]))

    # How bad is the damage, measured rather than assumed. A mix-up fuses the two
    # bibliographies into one state, and the question that decides whether this
    # needs a guard or a refusal is what the NEXT correct run says. If the fused
    # state made later verdicts wrong, this would have to refuse; if it only
    # leaves noise and a state nobody can take apart again, a warning plus a way
    # to prune is the proportionate answer.
    m = len(res) // 2
    a_lim, b_lim = res[:m], res[m:]
    limpio = refcheck.compara_vigilancia(estado_de(a_lim), copy.deepcopy(a_lim))
    fundido = refcheck.actualiza_vigilancia(estado_de(a_lim), copy.deepcopy(b_lim),
                                            ahora=2.0)
    despues = refcheck.compara_vigilancia(fundido, copy.deepcopy(a_lim))
    igual = all(len(limpio[k]) == len(despues[k]) for k in limpio)
    print("\nafter the mix-up, the next correct run over the right file:")
    for k in ("nuevos", "ausentes", "no_comprobados", "nuevas"):
        print("  %-15s clean state %3d · fused state %3d"
              % (k, len(limpio[k]), len(despues[k])))
    print("  verdicts changed by the fusion: %s" % ("no" if igual else "YES"))
    print("  references left in the state that this file does not contain: %d"
          % len(set(fundido["vistas"]) - claves(a_lim)))

    legit = [f["cobertura_del_estado"] for f in filas if f["legitimo"]]
    malo = [f["cobertura_del_estado"] for f in filas if not f["legitimo"]]
    print("\ncoverage of the state by the file:")
    print("  legitimate scenarios: %.1f%% – %.1f%%" % (100 * min(legit), 100 * max(legit)))
    print("  wrong file:           %.1f%%" % (100 * max(malo)))
    # The separation is what licenses a threshold. If these ever meet, the signal
    # is not good enough and the guard should not be built on it.
    print("  gap: %.1f points" % (100 * (min(legit) - max(malo))))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(filas, f, ensure_ascii=False, indent=1)
        print("\nwritten: %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
