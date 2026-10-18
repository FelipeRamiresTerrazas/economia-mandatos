"""Ponto de entrada único do pipeline: python -m src.main [etapas...] [--forcar]

Etapas implementadas: coleta. (tratamento, análise e relatório entram nas próximas etapas.)
"""
from __future__ import annotations

import argparse
import logging
import sys

from src import coleta

ETAPAS = {"coleta": None}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("etapas", nargs="*", choices=list(ETAPAS),
                   help="etapas a rodar (padrão: todas)")
    p.add_argument("--forcar", action="store_true",
                   help="ignora o cache em data/raw e baixa tudo de novo")
    p.add_argument("--series", nargs="+", metavar="ID",
                   help="coleta só estas séries (ids de config/series.yaml)")
    args = p.parse_args(argv)
    etapas = args.etapas or list(ETAPAS)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    falhas = 0
    if "coleta" in etapas:
        resumo = coleta.coletar(forcar=args.forcar, ids=args.series)
        falhas = int((resumo["status"] != "ok").sum())
        print(f"\nColeta: {len(resumo) - falhas} séries ok, {falhas} com erro.")
        if falhas:
            print(resumo.loc[resumo["status"] != "ok", ["id", "erro"]].to_string(index=False))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
