"""Séries derivadas: transformações declaradas em config/indicadores.yaml (`derivadas`).

Lê data/processed/series/ e grava data/processed/derivadas/<id>.csv com colunas `data, valor`.
As transformações são funções puras sobre DataFrames, testáveis offline.
"""
from __future__ import annotations

import logging

import pandas as pd

from src.config import (DERIVADAS_DIR, SERIES_DIR, carregar_catalogo, carregar_indicadores,
                        carregar_periodos)
from src.periodos import fim_do_periodo

log = logging.getLogger(__name__)

# um mês diário é considerado completo se a última cotação está a até 3 dias do fim do mês
_TOLERANCIA_FIM_DE_MES = pd.Timedelta(days=3)


# ------------------------------------------------------------------ leitura e metadados
def ler_serie(serie_id: str) -> pd.DataFrame:
    for pasta in (SERIES_DIR, DERIVADAS_DIR):
        caminho = pasta / f"{serie_id}.csv"
        if caminho.exists():
            return pd.read_csv(caminho, parse_dates=["data"])
    raise FileNotFoundError(f"série {serie_id} não encontrada em {SERIES_DIR} nem {DERIVADAS_DIR}")


def metadados() -> dict[str, dict]:
    """id -> {nome, unidade, frequencia, fonte, observacoes, origem, derivada} de toda série."""
    meta = {s["id"]: {**s, "fonte": s["coletor"], "derivada": False}
            for s in carregar_catalogo()["series"]}
    for d in carregar_indicadores()["derivadas"]:
        origem = meta[d["origem"]]
        meta[d["id"]] = {**d, "frequencia": frequencia_derivada(d, origem["frequencia"]),
                         "fonte": origem["fonte"], "derivada": True}
    return meta


def frequencia_derivada(spec: dict, freq_origem: str) -> str:
    if spec["tipo"] == "fim_de_ano":
        return "anual"
    if spec["tipo"] in ("media_mensal", "fim_de_mes", "juro_real_12m"):
        return "mensal"
    return freq_origem


# ------------------------------------------------------------------ transformações
def fim_de_ano(df: pd.DataFrame, frequencia: str) -> pd.DataFrame:
    """Valor do último período de cada ano (dezembro ou 4º trimestre); data = 1º/jan do ano.
    Anos sem o último período (ano em curso) ficam de fora."""
    fins = fim_do_periodo(df["data"], frequencia)
    sel = df[fins.dt.month == 12]
    return pd.DataFrame({"data": pd.to_datetime(sel["data"].dt.year.astype(str) + "-01-01"),
                         "valor": sel["valor"].to_numpy()})


def _meses_completos(df: pd.DataFrame) -> pd.Series:
    """Máscara que descarta o último mês de uma série diária se ele ainda não terminou."""
    ultima = df["data"].max()
    fim_mes = ultima + pd.offsets.MonthEnd(0)
    if fim_mes - ultima <= _TOLERANCIA_FIM_DE_MES:
        return pd.Series(True, index=df.index)
    return df["data"].dt.to_period("M") != ultima.to_period("M")


def media_mensal(df: pd.DataFrame) -> pd.DataFrame:
    df = df[_meses_completos(df)]
    g = df.groupby(df["data"].dt.to_period("M"))["valor"].mean()
    return pd.DataFrame({"data": g.index.to_timestamp(), "valor": g.to_numpy()})


def fim_de_mes(df: pd.DataFrame) -> pd.DataFrame:
    df = df[_meses_completos(df)].sort_values("data")
    g = df.groupby(df["data"].dt.to_period("M"))["valor"].last()
    return pd.DataFrame({"data": g.index.to_timestamp(), "valor": g.to_numpy()})


def media_movel(df: pd.DataFrame, janela: int) -> pd.DataFrame:
    df = df.sort_values("data")
    valores = df["valor"].rolling(janela, min_periods=janela).mean()
    return pd.DataFrame({"data": df["data"], "valor": valores}).dropna()


def acumulado_12m(taxas: pd.DataFrame) -> pd.DataFrame:
    """Taxa composta de 12 meses (em %) a partir de taxas mensais em %."""
    taxas = taxas.sort_values("data")
    fator = (1 + taxas["valor"] / 100).rolling(12, min_periods=12).apply(lambda x: x.prod(), raw=True)
    return pd.DataFrame({"data": taxas["data"], "valor": (fator - 1) * 100}).dropna()


def juro_real_12m(juro_mensal: pd.DataFrame, inflacao_mensal: pd.DataFrame) -> pd.DataFrame:
    """((1 + juro 12m) / (1 + inflação 12m) - 1) em %, só nos meses presentes nas duas séries."""
    j = acumulado_12m(juro_mensal)
    i = acumulado_12m(inflacao_mensal)
    m = j.merge(i, on="data", suffixes=("_j", "_i"))
    real = ((1 + m["valor_j"] / 100) / (1 + m["valor_i"] / 100) - 1) * 100
    return pd.DataFrame({"data": m["data"], "valor": real})


def deflacionar(df: pd.DataFrame, frequencia: str, indice: pd.DataFrame, ano_base: int) -> pd.DataFrame:
    """Valor a preços médios de `ano_base` pelo número-índice mensal `indice`.
    Séries anuais usam a média do índice nos 12 meses do ano; anos incompletos ficam de fora."""
    por_ano = indice.groupby(indice["data"].dt.year)["valor"].agg(["mean", "count"])
    medias = por_ano.loc[por_ano["count"] == 12, "mean"]
    if ano_base not in medias.index:
        raise ValueError(f"índice de preços sem os 12 meses do ano-base {ano_base}")
    base = medias.loc[ano_base]
    if frequencia == "anual":
        fator = df["data"].dt.year.map(medias)
    elif frequencia == "mensal":
        fator = df["data"].map(indice.set_index("data")["valor"])
    else:
        raise ValueError(f"deflação não implementada para frequência {frequencia}")
    out = pd.DataFrame({"data": df["data"], "valor": df["valor"] * base / fator})
    return out.dropna()


def derivar(spec: dict, meta: dict[str, dict], ano_base: int) -> pd.DataFrame:
    origem = ler_serie(spec["origem"])
    freq = meta[spec["origem"]]["frequencia"]
    tipo = spec["tipo"]
    if tipo == "fim_de_ano":
        df = fim_de_ano(origem, freq)
    elif tipo == "media_mensal":
        df = media_mensal(origem)
    elif tipo == "fim_de_mes":
        df = fim_de_mes(origem)
    elif tipo == "media_movel":
        df = media_movel(origem, int(spec["janela"]))
    elif tipo == "juro_real_12m":
        df = juro_real_12m(origem, ler_serie(spec["deflator"]))
    elif tipo == "deflacionar":
        df = deflacionar(origem, freq, ler_serie(spec["deflator"]), ano_base)
    elif tipo == "escala":
        df = origem[["data", "valor"]].copy()
    else:
        raise ValueError(f"tipo de derivada desconhecido: {tipo}")
    if "fator" in spec:
        df = df.assign(valor=df["valor"] * float(spec["fator"]))
    return df.reset_index(drop=True)


def tratar() -> int:
    """Gera todas as derivadas. Devolve o número de falhas (derivada com falha não é gravada)."""
    meta = metadados()
    ano_base = int(carregar_periodos()["ano_base_deflacao"])
    DERIVADAS_DIR.mkdir(parents=True, exist_ok=True)
    falhas = 0
    for spec in carregar_indicadores()["derivadas"]:
        caminho = DERIVADAS_DIR / f"{spec['id']}.csv"
        try:
            df = derivar(spec, meta, ano_base)
            if df.empty:
                raise ValueError("resultado vazio")
        except Exception as e:  # registra e segue; o indicador aparece como indisponível
            falhas += 1
            caminho.unlink(missing_ok=True)
            log.error("ERRO  %-22s %s: %s", spec["id"], type(e).__name__, e)
            continue
        df.to_csv(caminho, index=False, date_format="%Y-%m-%d")
        log.info("ok    %-22s %5d obs  %s a %s", spec["id"], len(df),
                 df["data"].min().date(), df["data"].max().date())
    return falhas
