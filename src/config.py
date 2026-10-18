"""Caminhos do projeto e leitura dos arquivos de configuração."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SERIES_DIR = PROCESSED_DIR / "series"
DERIVADAS_DIR = PROCESSED_DIR / "derivadas"
ANALISE_DIR = PROCESSED_DIR / "analise"
REPORTS_DIR = ROOT / "reports"


def _ler_yaml(nome: str) -> dict:
    with open(CONFIG_DIR / nome, encoding="utf-8") as f:
        return yaml.safe_load(f)


def carregar_catalogo() -> dict:
    """Retorna o conteúdo de config/series.yaml (chaves `padroes` e `series`)."""
    catalogo = _ler_yaml("series.yaml")
    ids = [s["id"] for s in catalogo["series"]]
    duplicados = {i for i in ids if ids.count(i) > 1}
    if duplicados:
        raise ValueError(f"ids duplicados em series.yaml: {sorted(duplicados)}")
    return catalogo


def carregar_periodos() -> dict:
    """Retorna o conteúdo de config/periodos.yaml."""
    return _ler_yaml("periodos.yaml")


def carregar_indicadores() -> dict:
    """Retorna o conteúdo de config/indicadores.yaml (chaves `derivadas`, `indicadores`, `pares`)."""
    cfg = _ler_yaml("indicadores.yaml")
    ids = [d["id"] for d in cfg["derivadas"]] + [s["id"] for s in carregar_catalogo()["series"]]
    duplicados = {i for i in ids if ids.count(i) > 1}
    if duplicados:
        raise ValueError(f"ids de série repetidos entre series.yaml e derivadas: {sorted(duplicados)}")
    return cfg
