"""Testes offline de tratamento e análise com casos simples calculados à mão."""
import pandas as pd
import pytest

from src import tratamento as t
from src.analise import Indisponivel, NaoSeAplica, calcular
from src.periodos import Periodo, fim_do_periodo, listar_periodos, n_esperado
from src.visualizacao.graficos import numero

TS = pd.Timestamp
MANDATO = Periodo("m", "M", TS("2003-01-01"), TS("2004-12-31"))
EM_CURSO = Periodo("c", "C", TS("2023-01-01"), None)
DILMA2 = Periodo("dilma2", "Dilma 2", TS("2015-01-01"), TS("2016-08-31"), pai="x")
TEMER = Periodo("temer", "Temer", TS("2016-09-01"), TS("2018-12-31"), pai="x")


def serie(datas, valores):
    return pd.DataFrame({"data": pd.to_datetime(datas), "valor": valores})


# ------------------------------------------------------------------ períodos
def test_periodos_do_yaml_tem_subperiodos_depois_do_mandato():
    ids = [p.id for p in listar_periodos()]
    assert ids.index("dilma2_temer") < ids.index("dilma2") < ids.index("temer") < ids.index("bolsonaro")


def test_fim_do_periodo_por_frequencia():
    d = pd.Series(pd.to_datetime(["2016-07-01"]))
    assert fim_do_periodo(d, "trimestral").iloc[0] == TS("2016-09-30")
    assert fim_do_periodo(d, "mensal").iloc[0] == TS("2016-07-31")
    assert fim_do_periodo(d, "anual").iloc[0] == TS("2016-12-31")


def test_n_esperado():
    assert n_esperado(TS("2003-01-01"), TS("2006-12-31"), "trimestral") == 16
    assert n_esperado(TS("2003-01-01"), TS("2006-12-31"), "anual") == 4
    assert n_esperado(TS("2016-09-01"), TS("2018-12-31"), "mensal") == 28


# ------------------------------------------------------------------ métricas
def test_media_geometrica_de_taxas_anuais():
    # (1,10 * 1,00) ^ (1/2) - 1 = 4,8809 %
    r = calcular(serie(["2003-01-01", "2004-01-01"], [10.0, 0.0]), "anual", MANDATO, "media_geometrica")
    assert r["valor"] == pytest.approx(4.8809, abs=1e-4)


def test_acumulado_composto():
    datas = pd.date_range("2003-01-01", "2004-12-01", freq="MS")
    valores = [1.0] + [0.0] * 22 + [1.0]          # 1,01 * 1,01 - 1 = 2,01 %
    r = calcular(serie(datas, valores), "mensal", MANDATO, "acumulado")
    assert r["valor"] == pytest.approx(2.01)
    assert r["n_obs"] == 24


def test_media_simples():
    r = calcular(serie(["2002-01-01", "2003-01-01", "2004-01-01"], [99, 2.0, 4.0]), "anual", MANDATO, "media")
    assert r["valor"] == 3.0


def test_inicio_fim_usa_ultima_observacao_antes_da_posse():
    df = serie(["2002-10-01", "2003-07-01", "2004-10-01"], [10.0, 12.0, 8.0])
    r = calcular(df, "trimestral", MANDATO, "inicio_fim")
    assert (r["valor_inicio"], r["valor_fim"], r["valor"]) == (10.0, 8.0, -2.0)


def test_variacao_pct():
    r = calcular(serie(["2002-01-01", "2004-01-01"], [200.0, 250.0]), "anual", MANDATO, "variacao_pct")
    assert r["valor"] == pytest.approx(25.0)


# ------------------------------------------------------------------ regras de cobertura
def test_cobertura_parcial_fica_indisponivel():
    with pytest.raises(Indisponivel, match="cobertura parcial: 1 de 2"):
        calcular(serie(["2004-01-01"], [3.0]), "anual", MANDATO, "media")


def test_sem_observacao_antes_do_inicio_fica_indisponivel():
    with pytest.raises(Indisponivel, match="anterior ao início"):
        calcular(serie(["2003-01-01", "2004-01-01"], [1.0, 2.0]), "anual", MANDATO, "inicio_fim")


def test_quebra_metodologica_bloqueia_comparacao():
    df = serie(["2010-01-01", "2014-01-01"], [50.0, 49.0])
    p = Periodo("d", "D", TS("2011-01-01"), TS("2014-12-31"))
    with pytest.raises(Indisponivel, match="quebra metodológica de 2012"):
        calcular(df, "anual", p, "inicio_fim", [TS("2012-01-01")])


def test_serie_anual_nao_vale_em_subperiodo():
    with pytest.raises(NaoSeAplica):
        calcular(serie(["2015-01-01"], [1.0]), "anual", DILMA2, "media")


def test_trimestre_2016T3_vai_para_temer():
    datas = pd.date_range("2015-01-01", "2018-10-01", freq="QS")
    df = serie(datas, range(len(datas)))
    assert calcular(df, "trimestral", DILMA2, "media")["data_fim"] == TS("2016-04-01")
    assert calcular(df, "trimestral", TEMER, "media")["data_inicio"] == TS("2016-07-01")


def test_mandato_em_curso_usa_so_o_observado():
    datas = pd.date_range("2022-12-01", "2023-03-01", freq="MS")
    r = calcular(serie(datas, [1.0, 1.0, 1.0, 1.0]), "mensal", EM_CURSO, "acumulado")
    assert r["n_obs"] == 3 and r["valor"] == pytest.approx(3.0301)


# ------------------------------------------------------------------ tratamento
def test_fim_de_ano_pega_dezembro_e_descarta_ano_incompleto():
    df = serie(["2023-11-01", "2023-12-01", "2024-01-01"], [1.0, 4.6, 4.5])
    out = t.fim_de_ano(df, "mensal")
    assert list(out["data"]) == [TS("2023-01-01")] and list(out["valor"]) == [4.6]


def test_fim_de_ano_trimestral_usa_4o_trimestre():
    out = t.fim_de_ano(serie(["2023-07-01", "2023-10-01"], [2.0, 3.2]), "trimestral")
    assert list(out["valor"]) == [3.2]


def test_media_mensal_descarta_mes_em_andamento():
    df = serie(["2026-09-29", "2026-09-30", "2026-10-15"], [5.0, 5.2, 9.9])
    out = t.media_mensal(df)
    assert list(out["data"]) == [TS("2026-09-01")] and out["valor"].iloc[0] == pytest.approx(5.1)


def test_juro_real_12m():
    datas = pd.date_range("2020-01-01", periods=12, freq="MS")
    juro = serie(datas, [1.0] * 12)               # 1,01^12 = 1,126825
    inflacao = serie(datas, [0.5] * 12)           # 1,005^12 = 1,061678
    out = t.juro_real_12m(juro, inflacao)
    assert len(out) == 1
    assert out["valor"].iloc[0] == pytest.approx((1.126825 / 1.061678 - 1) * 100, abs=1e-4)


def test_deflacionar_anual_pela_media_do_indice():
    indice = serie(pd.date_range("2020-01-01", "2021-12-01", freq="MS"), [100.0] * 12 + [110.0] * 12)
    out = t.deflacionar(serie(["2020-01-01", "2021-01-01"], [1000.0, 1100.0]), "anual", indice, 2021)
    assert list(out["valor"]) == pytest.approx([1100.0, 1100.0])


def test_deflacionar_exige_ano_base_completo():
    indice = serie(pd.date_range("2021-01-01", periods=6, freq="MS"), [100.0] * 6)
    with pytest.raises(ValueError, match="ano-base"):
        t.deflacionar(serie(["2021-01-01"], [1.0]), "anual", indice, 2021)


# ------------------------------------------------------------------ formatação
def test_numero_formato_brasileiro():
    assert numero(1234.5) == "1.234,5"
    assert numero(-0.25, 2, sinal=True) == "−0,25"
    assert numero(3.0, 1, sinal=True) == "+3,0"
