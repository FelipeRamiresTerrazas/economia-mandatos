"""Indicadores por período: aplica a mesma métrica de config/indicadores.yaml a todos os períodos.

Gera em data/processed/analise/:
  indicadores_por_periodo.csv   um registro por indicador x período (mandatos e subperíodos)
  pares_por_mandato.csv         indicadores do Banco Mundial para Brasil e pares, por mandato

Um resultado é "indisponivel" (com `motivo`) quando a série não cobre o período inteiro, quando
falta observação antes do início ou quando o cálculo atravessa uma quebra metodológica. Nada é
estimado. No mandato em curso usa-se o que foi observado até o último dado, sem anualizar.
"""
from __future__ import annotations

import logging
import math

import pandas as pd

from src.config import ANALISE_DIR, carregar_catalogo, carregar_indicadores
from src.periodos import Periodo, fim_do_periodo, listar_periodos, n_esperado
from src.tratamento import ler_serie, metadados

log = logging.getLogger(__name__)

METRICAS_JANELA = {"media", "media_geometrica", "acumulado"}
METRICAS_PONTA = {"inicio_fim", "variacao_pct"}
# defasagem máxima entre a observação usada e a borda do período (cobre lacunas de anos de censo)
DEFASAGEM_MAXIMA = pd.Timedelta(days=550)


class Indisponivel(Exception):
    """O indicador não pode ser calculado para o período; a mensagem é o motivo."""


class NaoSeAplica(Indisponivel):
    """A combinação série x período não é calculada por convenção (ex.: série anual em subperíodo)."""


def _fmt_data(ts: pd.Timestamp, frequencia: str) -> str:
    if frequencia == "anual":
        return f"{ts.year}"
    if frequencia == "trimestral":
        return f"{ts.year}T{(ts.month - 1) // 3 + 1}"
    return f"{ts.month:02d}/{ts.year}"


def _preparar(df: pd.DataFrame, frequencia: str) -> pd.DataFrame:
    df = df.dropna(subset=["valor"]).sort_values("data").reset_index(drop=True)
    return df.assign(fim=fim_do_periodo(df["data"], frequencia))


def _checar_quebras(primeira: pd.Timestamp, ultima: pd.Timestamp, quebras: list[pd.Timestamp]) -> None:
    for q in quebras:
        if primeira < q <= ultima:
            raise Indisponivel(f"atravessa a quebra metodológica de {q.year}")


def calcular(df: pd.DataFrame, frequencia: str, periodo: Periodo, metrica: str,
             quebras: list[pd.Timestamp] | None = None) -> dict:
    """Aplica `metrica` à série `df` (colunas data, valor) no `periodo`. Levanta Indisponivel."""
    quebras = quebras or []
    if frequencia == "anual" and not periodo.anos_inteiros:
        raise NaoSeAplica("série anual não é dividida em subperíodos que cortam o ano")
    df = _preparar(df, frequencia)
    if df.empty:
        raise Indisponivel("série sem observações")
    limite = periodo.fim if periodo.fim is not None else df["fim"].max()
    dentro = df[(df["fim"] >= periodo.inicio) & (df["fim"] <= limite)]
    cobertura = (f"série disponível de {_fmt_data(df['data'].iloc[0], frequencia)} "
                 f"a {_fmt_data(df['data'].iloc[-1], frequencia)}")
    if dentro.empty:
        raise Indisponivel(f"sem observações no período ({cobertura})")

    if metrica in METRICAS_JANELA:
        esperado = n_esperado(periodo.inicio, limite, frequencia)
        if len(dentro) < esperado:
            raise Indisponivel(f"cobertura parcial: {len(dentro)} de {esperado} períodos ({cobertura})")
        _checar_quebras(dentro["data"].iloc[0], dentro["data"].iloc[-1], quebras)
        v = dentro["valor"]
        if metrica == "media":
            valor = v.mean()
        elif metrica == "media_geometrica":
            valor = (math.prod(1 + v / 100) ** (1 / len(v)) - 1) * 100
        else:
            valor = (math.prod(1 + v / 100) - 1) * 100
        return {"valor": valor, "data_inicio": dentro["data"].iloc[0], "data_fim": dentro["data"].iloc[-1],
                "n_obs": len(dentro), "n_esperado": esperado}

    if metrica in METRICAS_PONTA:
        antes = df[df["fim"] < periodo.inicio]
        if antes.empty:
            raise Indisponivel(f"sem observação anterior ao início ({cobertura})")
        ini, fim = antes.iloc[-1], dentro.iloc[-1]
        if periodo.inicio - ini["fim"] > DEFASAGEM_MAXIMA:
            raise Indisponivel(f"última observação antes do início é de {_fmt_data(ini['data'], frequencia)}")
        if periodo.fim is not None and periodo.fim - fim["fim"] > DEFASAGEM_MAXIMA:
            raise Indisponivel(f"última observação do período é de {_fmt_data(fim['data'], frequencia)}")
        _checar_quebras(ini["data"], fim["data"], quebras)
        if metrica == "inicio_fim":
            valor = fim["valor"] - ini["valor"]
        else:
            if ini["valor"] == 0:
                raise Indisponivel("valor inicial igual a zero")
            valor = (fim["valor"] / ini["valor"] - 1) * 100
        return {"valor": valor, "valor_inicio": ini["valor"], "valor_fim": fim["valor"],
                "data_inicio": ini["data"], "data_fim": fim["data"], "n_obs": 2}

    raise ValueError(f"métrica desconhecida: {metrica}")


def _resultado(base: dict, df: pd.DataFrame | None, frequencia: str, periodo: Periodo,
               metrica: str, quebras: list) -> dict:
    linha = {**base, "periodo": periodo.id, "em_curso": periodo.em_curso}
    try:
        if df is None:
            raise Indisponivel("série não foi gerada (ver log da coleta/tratamento)")
        r = calcular(df, frequencia, periodo, metrica, quebras)
        linha.update(status="ok", motivo="", **r)
        for k in ("data_inicio", "data_fim"):
            linha[k] = _fmt_data(linha[k], frequencia)
    except NaoSeAplica as e:
        linha.update(status="nao_se_aplica", motivo=str(e))
    except Indisponivel as e:
        linha.update(status="indisponivel", motivo=str(e))
    return linha


def _ler(serie_id: str, pais: str | None = None) -> pd.DataFrame | None:
    try:
        df = ler_serie(serie_id)
    except FileNotFoundError:
        return None
    if pais is not None:
        df = df[df["pais"] == pais]
    return df[["data", "valor"]]


COLUNAS = ["indicador", "periodo", "status", "valor", "valor_inicio", "valor_fim", "data_inicio",
           "data_fim", "n_obs", "n_esperado", "em_curso", "motivo"]


def analisar() -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = carregar_indicadores()
    meta = metadados()
    periodos = listar_periodos()

    linhas = []
    for ind in cfg["indicadores"]:
        freq = meta[ind["serie"]]["frequencia"]
        df = _ler(ind["serie"], ind.get("pais"))
        quebras = [pd.Timestamp(q) for q in ind.get("quebra", [])]
        for p in periodos:
            linhas.append(_resultado({"indicador": ind["id"]}, df, freq, p, ind["metrica"], quebras))
    indicadores = pd.DataFrame(linhas).reindex(columns=COLUNAS)

    paises = carregar_catalogo()["padroes"]["worldbank_paises"]
    linhas = []
    for par in cfg["pares"]:
        freq = meta[par["serie"]]["frequencia"]
        for pais in paises:
            df = _ler(par["serie"], pais)
            for p in periodos:
                if p.pai is None:
                    linhas.append(_resultado({"indicador": par["id"], "pais": pais}, df, freq, p,
                                             par["metrica"], []))
    pares = pd.DataFrame(linhas).reindex(columns=COLUNAS[:1] + ["pais"] + COLUNAS[1:])

    ANALISE_DIR.mkdir(parents=True, exist_ok=True)
    indicadores.to_csv(ANALISE_DIR / "indicadores_por_periodo.csv", index=False)
    pares.to_csv(ANALISE_DIR / "pares_por_mandato.csv", index=False)
    for nome, t in (("indicadores", indicadores), ("pares", pares)):
        c = t["status"].value_counts()
        log.info("%-11s %d ok, %d indisponíveis, %d não se aplica", nome, c.get("ok", 0),
                 c.get("indisponivel", 0), c.get("nao_se_aplica", 0))
    return indicadores, pares
