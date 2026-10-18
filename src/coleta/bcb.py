"""Coletor Banco Central do Brasil / SGS (https://api.bcb.gov.br/dados/serie/bcdata.sgs.<codigo>/dados).

O SGS limita consultas de séries diárias a 10 anos por requisição; por isso a coleta é feita em
janelas de 5 anos, para todas as séries. Uma janela sem dados volta como HTTP 404 e é ignorada.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.coleta.base import Bruto, SemDados, agora_iso, get_json

FONTE = "bcb"
URL_SERIE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
ANOS_POR_JANELA = 5


def janelas(inicio: date, fim: date, anos: int = ANOS_POR_JANELA) -> list[tuple[date, date]]:
    """Divide [inicio, fim] em janelas consecutivas de até `anos` anos civis."""
    saida = []
    a = inicio
    while a <= fim:
        b = min(date(a.year + anos - 1, 12, 31), fim)
        saida.append((a, b))
        a = date(b.year + 1, 1, 1)
    return saida


def baixar(spec: dict, padroes: dict) -> Bruto:
    codigo = spec["codigo"]["sgs"]
    inicio = pd.Timestamp(padroes["inicio_coleta"]).date()
    respostas, urls = [], []
    for a, b in janelas(inicio, date.today()):
        params = {
            "formato": "json",
            "dataInicial": a.strftime("%d/%m/%Y"),
            "dataFinal": b.strftime("%d/%m/%Y"),
        }
        try:
            dados, url = get_json(URL_SERIE.format(codigo=codigo), params)
        except SemDados:
            continue
        respostas.append(dados)
        urls.append(url)
    return Bruto(spec["id"], FONTE, spec["codigo"], respostas, urls, agora_iso())


def parsear(respostas: list, spec: dict | None = None, baixado_em: str | None = None) -> pd.DataFrame:
    registros = [r for lote in respostas for r in lote]
    df = pd.DataFrame(
        {
            "data": pd.to_datetime([r["data"] for r in registros], format="%d/%m/%Y"),
            "valor": pd.to_numeric([r["valor"] for r in registros], errors="coerce"),
        }
    )
    df = df.dropna(subset=["valor"]).drop_duplicates("data").sort_values("data")
    if baixado_em:
        # A meta Selic (SGS 432) vem com datas futuras; só fica o que já tinha ocorrido no download.
        corte = pd.Timestamp(baixado_em[:10])
        df = df[df["data"] <= corte]
    return df.reset_index(drop=True)
