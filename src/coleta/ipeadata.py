"""Coletor IPEADATA (API OData v4: http://www.ipeadata.gov.br/api/odata4).

Baixa valores e o registro de metadados da série (nome, fonte original, comentário metodológico),
que fica guardado junto do bruto.
"""
from __future__ import annotations

import pandas as pd

from src.coleta.base import Bruto, agora_iso, get_json

FONTE = "ipeadata"
URL_BASE = "http://www.ipeadata.gov.br/api/odata4"


def baixar(spec: dict, padroes: dict, fonte: str = FONTE) -> Bruto:
    sercodigo = spec["codigo"]["sercodigo"]
    meta, url_meta = get_json(f"{URL_BASE}/Metadados('{sercodigo}')")
    valores, url_valores = get_json(f"{URL_BASE}/ValoresSerie(SERCODIGO='{sercodigo}')")
    if not meta.get("value"):
        raise ValueError(f"IPEADATA não tem metadados para {sercodigo}")
    m = meta["value"][0]
    extra = {
        "ipeadata_nome": m.get("SERNOME"),
        "ipeadata_fonte_original": m.get("FNTNOME"),
        "ipeadata_unidade": m.get("UNINOME"),
        "ipeadata_multiplicador": m.get("MULNOME"),
        "ipeadata_atualizacao": m.get("SERATUALIZACAO"),
        "ipeadata_status": m.get("SERSTATUS"),
    }
    return Bruto(spec["id"], fonte, spec["codigo"], [meta, valores],
                 [url_meta, url_valores], agora_iso(), extra)


def parsear(respostas: list, spec: dict | None = None, baixado_em: str | None = None) -> pd.DataFrame:
    valores = respostas[1]["value"]
    # Séries nacionais têm nível territorial vazio ou "Brasil"; descarta recortes regionais, se houver.
    nacionais = [v for v in valores if (v.get("NIVNOME") or "Brasil") == "Brasil"]
    df = pd.DataFrame(
        {
            "data": pd.to_datetime([v["VALDATA"][:10] for v in nacionais]),
            "valor": pd.to_numeric([v["VALVALOR"] for v in nacionais], errors="coerce"),
        }
    )
    df = df.dropna(subset=["valor"]).sort_values("data").reset_index(drop=True)
    if df["data"].duplicated().any():
        raise ValueError("datas duplicadas na série do IPEADATA")
    return df
