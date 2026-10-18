"""Testes offline dos coletores: parsers sobre respostas mínimas no formato real de cada API."""
from datetime import date

import pandas as pd
import pytest

from src.coleta import base, bcb, ibge, ipeadata, worldbank
from src.config import carregar_catalogo


# ------------------------------------------------------------------ IBGE / SIDRA
def _sidra(rotulo_periodo, linhas):
    cab = {"V": "Valor", "D3C": rotulo_periodo}
    return [[cab] + [{"V": v, "D3C": c} for c, v in linhas]]


def test_sidra_trimestre_vira_primeiro_dia_do_trimestre():
    df = ibge.parsear(_sidra("Trimestre (Código)", [("201201", "7.9"), ("201204", "6.9")]))
    assert list(df["data"]) == [pd.Timestamp(2012, 1, 1), pd.Timestamp(2012, 10, 1)]
    assert list(df["valor"]) == [7.9, 6.9]


def test_sidra_trimestre_movel_usa_ultimo_mes():
    df = ibge.parsear(_sidra("Trimestre Móvel (Código)", [("201203", "8.0")]))
    assert df["data"].iloc[0] == pd.Timestamp(2012, 3, 1)


def test_sidra_mes_e_ano():
    assert ibge.parsear(_sidra("Mês (Código)", [("200212", "2.1")]))["data"].iloc[0] == pd.Timestamp(2002, 12, 1)
    assert ibge.parsear(_sidra("Ano (Código)", [("2023", "1")]))["data"].iloc[0] == pd.Timestamp(2023, 1, 1)


@pytest.mark.parametrize("simbolo", ["-", "..", "...", "X", ""])
def test_sidra_simbolos_especiais_nao_viram_numero(simbolo):
    df = ibge.parsear(_sidra("Ano (Código)", [("2020", simbolo), ("2021", "-1.5")]))
    assert list(df["valor"]) == [-1.5]


def test_sidra_url_com_classificacao():
    url = ibge.montar_url({"tabela": 1620, "variavel": 583, "classificacoes": {11255: 90707}})
    assert url == "https://apisidra.ibge.gov.br/values/t/1620/n1/all/v/583/p/all/c11255/90707"


def test_sidra_periodo_duplicado_falha():
    with pytest.raises(ValueError):
        ibge.parsear(_sidra("Ano (Código)", [("2020", "1"), ("2020", "2")]))


# ------------------------------------------------------------------ BCB / SGS
def test_janelas_cobrem_intervalo_sem_buracos():
    j = bcb.janelas(date(2000, 1, 1), date(2011, 3, 15), anos=5)
    assert j == [
        (date(2000, 1, 1), date(2004, 12, 31)),
        (date(2005, 1, 1), date(2009, 12, 31)),
        (date(2010, 1, 1), date(2011, 3, 15)),
    ]


def test_bcb_concatena_lotes_remove_duplicata_e_corta_futuro():
    lotes = [
        [{"data": "30/12/2004", "valor": "17.75"}],
        [{"data": "30/12/2004", "valor": "17.75"}, {"data": "03/01/2005", "valor": "17.75"},
         {"data": "20/11/2026", "valor": "13.50"}],
    ]
    df = bcb.parsear(lotes, baixado_em="2026-10-16T20:00:00-03:00")
    assert list(df["data"]) == [pd.Timestamp(2004, 12, 30), pd.Timestamp(2005, 1, 3)]


# ------------------------------------------------------------------ IPEADATA
def test_ipeadata_filtra_nivel_nacional():
    valores = {"value": [
        {"VALDATA": "2024-01-01T00:00:00-03:00", "VALVALOR": 50.4, "NIVNOME": ""},
        {"VALDATA": "2024-01-01T00:00:00-03:00", "VALVALOR": 45.0, "NIVNOME": "Estados"},
        {"VALDATA": "2025-01-01T00:00:00-03:00", "VALVALOR": None, "NIVNOME": ""},
    ]}
    df = ipeadata.parsear([{}, valores])
    assert list(df["valor"]) == [50.4]


# ------------------------------------------------------------------ Banco Mundial
def test_worldbank_mapeia_agregado_sem_iso3():
    pagina = [{"page": 1, "pages": 1}, [
        {"countryiso3code": "BRA", "country": {"id": "BR"}, "date": "2024", "value": 9000.0},
        {"countryiso3code": "", "country": {"id": "XT"}, "date": "2024", "value": 11000.0},
        {"countryiso3code": "WLD", "country": {"id": "1W"}, "date": "2024", "value": None},
    ]]
    df = worldbank.parsear([pagina])
    assert set(df["pais"]) == {"BRA", "UMC"}


# ------------------------------------------------------------------ cache
def test_cache_detecta_edicao_manual(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "RAW_DIR", tmp_path)
    b = base.Bruto("x", "teste", {"sgs": 1}, [[{"data": "01/01/2020", "valor": "1"}]], ["u"], "2026-01-01")
    base.salvar_bruto(b)
    assert base.carregar_bruto("teste", "x").respostas == b.respostas
    (tmp_path / "teste" / "x.json").write_text("[]", encoding="utf-8")
    with pytest.raises(base.ColetaErro):
        base.carregar_bruto("teste", "x")


# ------------------------------------------------------------------ catálogo
def test_catalogo_tem_campos_obrigatorios_e_coletor_valido():
    from src.coleta import COLETORES
    for s in carregar_catalogo()["series"]:
        for campo in ("id", "nome", "coletor", "codigo", "unidade", "frequencia", "dimensao", "confirmado_em"):
            assert campo in s, (s.get("id"), campo)
        assert s["coletor"] in COLETORES, s["id"]
