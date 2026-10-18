"""Orquestra a coleta de todas as séries do catálogo.

Para cada série: usa o cache bruto (data/raw) se existir, senão baixa; normaliza para
data/processed/series/<id>.csv; registra o resultado em data/processed/coleta_resumo.csv.
Falhas não interrompem as demais séries e nunca são preenchidas com valores aproximados.
"""
from __future__ import annotations

import logging

import pandas as pd

from src.coleta import anp, bcb, ibge, ipeadata, worldbank
from src.coleta.base import carregar_bruto, salvar_bruto
from src.config import PROCESSED_DIR, SERIES_DIR, carregar_catalogo

COLETORES = {m.FONTE: m for m in (ibge, bcb, ipeadata, worldbank, anp)}
log = logging.getLogger(__name__)


def coletar_serie(spec: dict, padroes: dict, forcar: bool = False) -> dict:
    coletor = COLETORES[spec["coletor"]]
    bruto = None if forcar else carregar_bruto(coletor.FONTE, spec["id"])
    origem = "cache"
    if bruto is None:
        bruto = coletor.baixar(spec, padroes)
        salvar_bruto(bruto)
        origem = "download"
    df = coletor.parsear(bruto.respostas, spec, bruto.baixado_em)
    if df.empty:
        raise ValueError("a fonte respondeu, mas sem nenhum valor numérico")
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(SERIES_DIR / f"{spec['id']}.csv", index=False, date_format="%Y-%m-%d")
    resumo = {
        "id": spec["id"],
        "status": "ok",
        "origem": origem,
        "n_obs": len(df),
        "primeira_data": df["data"].min().date().isoformat(),
        "ultima_data": df["data"].max().date().isoformat(),
        "baixado_em": bruto.baixado_em,
        "erro": "",
    }
    if "pais" in df:
        resumo["paises"] = ",".join(sorted(df["pais"].unique()))
    return resumo


def coletar(forcar: bool = False, ids: list[str] | None = None) -> pd.DataFrame:
    catalogo = carregar_catalogo()
    padroes = catalogo["padroes"]
    specs = [s for s in catalogo["series"] if not ids or s["id"] in ids]
    if ids and len(specs) != len(set(ids)):
        faltando = set(ids) - {s["id"] for s in specs}
        raise ValueError(f"ids não encontrados em series.yaml: {sorted(faltando)}")

    linhas = []
    for spec in specs:
        base = {"id": spec["id"], "fonte": spec["coletor"], "codigo": str(spec["codigo"])}
        try:
            r = coletar_serie(spec, padroes, forcar)
            log.info("ok    %-28s %5d obs  %s a %s (%s)", spec["id"], r["n_obs"],
                     r["primeira_data"], r["ultima_data"], r["origem"])
        except Exception as e:  # registra e segue: série faltante vira "indisponível", não chute
            r = {"id": spec["id"], "status": "erro", "erro": f"{type(e).__name__}: {e}"}
            log.error("ERRO  %-28s %s", spec["id"], r["erro"])
        linhas.append({**base, **r})

    resumo = pd.DataFrame(linhas)
    if not ids:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        resumo.to_csv(PROCESSED_DIR / "coleta_resumo.csv", index=False)
    return resumo
