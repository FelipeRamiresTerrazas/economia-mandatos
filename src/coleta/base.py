"""Infraestrutura comum aos coletores: HTTP com retry, cache bruto em data/raw e metadados.

Cada série baixada gera dois arquivos em data/raw/<fonte>/:
  <id>.json       resposta da API exatamente como recebida (lista de respostas, uma por requisição)
  <id>.meta.json  fonte, código, URLs requisitadas, data/hora de download e hash SHA-256 do bruto
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import RAW_DIR

USER_AGENT = "economia-mandatos/0.1 (pesquisa reprodutivel com dados publicos)"
TIMEOUT = 120


class ColetaErro(RuntimeError):
    """Falha de coleta que deve ser reportada (nunca substituída por valor aproximado)."""


class SemDados(ColetaErro):
    """A fonte respondeu que não há dados no intervalo pedido (ex.: HTTP 404 do SGS)."""


@dataclass
class Bruto:
    serie_id: str
    fonte: str
    codigo: dict
    respostas: list
    urls: list[str]
    baixado_em: str
    extra: dict = field(default_factory=dict)


_sessao: requests.Session | None = None


def sessao() -> requests.Session:
    global _sessao
    if _sessao is None:
        s = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
        )
        adaptador = HTTPAdapter(max_retries=retry)
        s.mount("https://", adaptador)
        s.mount("http://", adaptador)
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        _sessao = s
    return _sessao


def get_json(url: str, params: dict | None = None, tentativas: int = 4) -> tuple[object, str]:
    """GET que devolve (json, url_final). Repete quando a resposta não é JSON válido,
    o que acontece em APIs sob limite de taxa que respondem HTML com status 200."""
    ultimo_erro: Exception | None = None
    for i in range(tentativas):
        try:
            r = sessao().get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            ultimo_erro = e
        else:
            if r.status_code == 404:
                raise SemDados(f"HTTP 404 em {r.url}")
            if r.ok:
                try:
                    return r.json(), r.url
                except ValueError as e:
                    ultimo_erro = ColetaErro(f"resposta não-JSON de {r.url}: {r.text[:120]!r}")
            else:
                ultimo_erro = ColetaErro(f"HTTP {r.status_code} em {r.url}")
        time.sleep(3 * (i + 1))
    raise ColetaErro(f"falha após {tentativas} tentativas: {ultimo_erro}")


def agora_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _caminhos(fonte: str, serie_id: str) -> tuple[Path, Path]:
    pasta = RAW_DIR / fonte
    return pasta / f"{serie_id}.json", pasta / f"{serie_id}.meta.json"


def salvar_bruto(b: Bruto) -> dict:
    dados, meta = _caminhos(b.fonte, b.serie_id)
    dados.parent.mkdir(parents=True, exist_ok=True)
    conteudo = json.dumps(b.respostas, ensure_ascii=False, indent=1).encode("utf-8")
    dados.write_bytes(conteudo)
    metadados = {
        "serie_id": b.serie_id,
        "fonte": b.fonte,
        "codigo": b.codigo,
        "urls": b.urls,
        "baixado_em": b.baixado_em,
        "sha256": hashlib.sha256(conteudo).hexdigest(),
        **b.extra,
    }
    meta.write_text(json.dumps(metadados, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadados


def carregar_bruto(fonte: str, serie_id: str) -> Bruto | None:
    """Lê o cache bruto; devolve None se não existe. Confere o hash para detectar edição manual."""
    dados, meta = _caminhos(fonte, serie_id)
    if not (dados.exists() and meta.exists()):
        return None
    conteudo = dados.read_bytes()
    m = json.loads(meta.read_text(encoding="utf-8"))
    if hashlib.sha256(conteudo).hexdigest() != m["sha256"]:
        raise ColetaErro(
            f"{dados} não confere com o hash registrado; o bruto foi alterado. "
            "Rode novamente com --forcar para baixar de novo."
        )
    extra = {k: v for k, v in m.items()
             if k not in {"serie_id", "fonte", "codigo", "urls", "baixado_em", "sha256"}}
    return Bruto(m["serie_id"], m["fonte"], m["codigo"], json.loads(conteudo),
                 m["urls"], m["baixado_em"], extra)
