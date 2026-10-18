"""Ponto de entrada único do pipeline: python -m src.main [etapas...] [--forcar]

Etapas, na ordem: coleta -> tratamento -> analise -> relatorio. Sem argumentos roda todas.
"""
from __future__ import annotations

import argparse
import logging
import sys

from src import analise, coleta, tratamento, visualizacao

ETAPAS = ["coleta", "tratamento", "analise", "relatorio"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("etapas", nargs="*", choices=ETAPAS,
                   help="etapas a rodar (padrão: todas)")
    p.add_argument("--forcar", action="store_true",
                   help="ignora o cache em data/raw e baixa tudo de novo")
    p.add_argument("--series", nargs="+", metavar="ID",
                   help="coleta só estas séries (ids de config/series.yaml)")
    args = p.parse_args(argv)
    etapas = args.etapas or ETAPAS
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    falhas = 0
    if "coleta" in etapas:
        resumo = coleta.coletar(forcar=args.forcar, ids=args.series)
        n = int((resumo["status"] != "ok").sum())
        print(f"\nColeta: {len(resumo) - n} séries ok, {n} com erro.")
        if n:
            print(resumo.loc[resumo["status"] != "ok", ["id", "erro"]].to_string(index=False))
        falhas += n
    if "tratamento" in etapas:
        n = tratamento.tratar()
        print(f"Tratamento: {n} derivadas com erro.")
        falhas += n
    if "analise" in etapas:
        analise.analisar()
    if "relatorio" in etapas:
        destino = visualizacao.gerar_relatorio()
        print(f"Relatório: {destino}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
