"""Coletor IBGE / SIDRA (https://apisidra.ibge.gov.br).

Sempre nível Brasil (n1), todos os períodos. Classificações (ex.: setor 90707 = PIB a preços de
mercado; sexo 6794 = Total) vêm de config/series.yaml.
"""
from __future__ import annotations

import re

import pandas as pd

from src.coleta.base import Bruto, agora_iso, get_json

FONTE = "ibge"
URL_BASE = "https://apisidra.ibge.gov.br/values"

# Rótulo da dimensão de período no cabeçalho da resposta -> função que converte o código em data.
_PERIODOS = {
    "Mês (Código)": lambda c: pd.Timestamp(int(c[:4]), int(c[4:6]), 1),
    "Trimestre (Código)": lambda c: pd.Timestamp(int(c[:4]), 3 * (int(c[4:6]) - 1) + 1, 1),
    # Trimestre móvel: código AAAAMM do último mês (201203 = jan-fev-mar 2012).
    "Trimestre Móvel (Código)": lambda c: pd.Timestamp(int(c[:4]), int(c[4:6]), 1),
    "Ano (Código)": lambda c: pd.Timestamp(int(c[:4]), 1, 1),
}


def montar_url(codigo: dict) -> str:
    url = f"{URL_BASE}/t/{codigo['tabela']}/n1/all/v/{codigo['variavel']}/p/all"
    for classif, categoria in (codigo.get("classificacoes") or {}).items():
        url += f"/c{classif}/{categoria}"
    return url


def baixar(spec: dict, padroes: dict) -> Bruto:
    url = montar_url(spec["codigo"])
    resposta, url_final = get_json(url)
    return Bruto(spec["id"], FONTE, spec["codigo"], [resposta], [url_final], agora_iso())


def _numero(v: str) -> float | None:
    """SIDRA usa '-', '..', '...', 'X' para zero absoluto / não aplicável / não disponível / sigilo.
    Nenhum desses vira número: todos são tratados como ausentes."""
    if v is None or not re.fullmatch(r"-?\d+(\.\d+)?", v.strip()):
        return None
    return float(v)


def parsear(respostas: list, spec: dict | None = None, baixado_em: str | None = None) -> pd.DataFrame:
    linhas = respostas[0]
    cabecalho, registros = linhas[0], linhas[1:]
    chave_periodo = next(
        (k for k, rotulo in cabecalho.items() if rotulo in _PERIODOS), None
    )
    if chave_periodo is None:
        raise ValueError(f"dimensão de período não reconhecida no cabeçalho: {cabecalho}")
    conversor = _PERIODOS[cabecalho[chave_periodo]]
    df = pd.DataFrame(
        {
            "data": [conversor(r[chave_periodo]) for r in registros],
            "valor": [_numero(r["V"]) for r in registros],
        }
    )
    df = df.dropna(subset=["valor"]).sort_values("data").reset_index(drop=True)
    if df["data"].duplicated().any():
        raise ValueError("períodos duplicados na resposta do SIDRA; confira as classificações")
    return df
