"""Coletor ANP (produção de petróleo).

O portal de dados abertos da ANP não oferece API estável (a página não expõe links diretos e a API
do dados.gov.br exige autenticação). A série mensal da ANP é obtida pela republicação no IPEADATA,
que registra a ANP como fonte original; o bruto fica em data/raw/anp/ para manter a separação por fonte.
"""
from __future__ import annotations

import pandas as pd

from src.coleta import ipeadata
from src.coleta.base import Bruto

FONTE = "anp"


def baixar(spec: dict, padroes: dict) -> Bruto:
    bruto = ipeadata.baixar(spec, padroes, fonte=FONTE)
    bruto.extra["intermediario"] = "IPEADATA"
    return bruto


def parsear(respostas: list, spec: dict | None = None, baixado_em: str | None = None) -> pd.DataFrame:
    return ipeadata.parsear(respostas, spec, baixado_em)
