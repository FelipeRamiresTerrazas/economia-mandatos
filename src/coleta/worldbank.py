"""Coletor Banco Mundial (API v2: https://api.worldbank.org/v2).

Brasil e agregados de comparação definidos em config/series.yaml (padroes.worldbank_paises).
"""
from __future__ import annotations

import pandas as pd

from src.coleta.base import Bruto, agora_iso, get_json

FONTE = "worldbank"
URL = "https://api.worldbank.org/v2/country/{paises}/indicator/{indicador}"

# Na resposta, alguns agregados vêm sem countryiso3code e só com o id de 2 letras.
_ID_PARA_CODIGO = {"XT": "UMC", "ZJ": "LCN", "1W": "WLD", "BR": "BRA", "XO": "LMY", "XP": "MIC"}


def baixar(spec: dict, padroes: dict) -> Bruto:
    paises = ";".join(padroes["worldbank_paises"])
    ano_inicio = pd.Timestamp(padroes["inicio_coleta"]).year
    url = URL.format(paises=paises, indicador=spec["codigo"]["indicador"])
    respostas, urls, pagina, paginas = [], [], 1, 1
    while pagina <= paginas:
        params = {"format": "json", "date": f"{ano_inicio}:{pd.Timestamp.today().year}",
                  "per_page": 1000, "page": pagina}
        dados, url_final = get_json(url, params)
        if not isinstance(dados, list) or len(dados) < 2:
            raise ValueError(f"resposta inesperada do Banco Mundial: {str(dados)[:200]}")
        respostas.append(dados)
        urls.append(url_final)
        paginas = int(dados[0]["pages"])
        pagina += 1
    extra = {"worldbank_lastupdated": respostas[0][0].get("lastupdated")}
    return Bruto(spec["id"], FONTE, spec["codigo"], respostas, urls, agora_iso(), extra)


def _codigo_pais(r: dict) -> str:
    return r.get("countryiso3code") or _ID_PARA_CODIGO.get(r["country"]["id"], r["country"]["id"])


def parsear(respostas: list, spec: dict | None = None, baixado_em: str | None = None) -> pd.DataFrame:
    registros = [r for pagina in respostas for r in (pagina[1] or [])]
    df = pd.DataFrame(
        {
            "pais": [_codigo_pais(r) for r in registros],
            "data": [pd.Timestamp(int(r["date"]), 1, 1) for r in registros],
            "valor": pd.to_numeric([r["value"] for r in registros], errors="coerce"),
        }
    )
    df = df.dropna(subset=["valor"]).sort_values(["pais", "data"]).reset_index(drop=True)
    if df.duplicated(["pais", "data"]).any():
        raise ValueError("pares (país, ano) duplicados na resposta do Banco Mundial")
    return df[["data", "pais", "valor"]]
