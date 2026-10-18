"""Relatório HTML: reports/relatorio.html, arquivo único (CSS, JS e gráficos SVG embutidos).

Todo número do relatório sai de data/processed/analise/*.csv ou de data/processed/{series,derivadas}.
O texto fixo deste módulo descreve método e limitações; não contém valores.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.analise import _fmt_data
from src.config import (ANALISE_DIR, PROCESSED_DIR, REPORTS_DIR, carregar_catalogo,
                        carregar_indicadores, carregar_periodos)
from src.periodos import Periodo, fim_do_periodo, listar_periodos
from src.tratamento import ler_serie, metadados
from src.visualizacao.graficos import grafico_linhas, numero

log = logging.getLogger(__name__)
AQUI = Path(__file__).resolve().parent
FONTES = {"ibge": "IBGE/SIDRA", "bcb": "Banco Central/SGS", "ipeadata": "IPEADATA",
          "anp": "ANP (via IPEADATA)", "worldbank": "Banco Mundial"}
X_INICIO = pd.Timestamp("2002-01-01")
e = html.escape


# ------------------------------------------------------------------ formatação de células
def _unidade_variacao(ind: dict) -> str:
    if ind["metrica"] == "variacao_pct":
        return "%"
    return "p.p." if "%" in ind["unidade"] else ind["unidade"]


def celula(r: pd.Series, ind: dict, notas: dict) -> str:
    casas = int(ind.get("casas", 1))
    classe = ' class="subp"' if r["_sub"] else ""
    if r["status"] != "ok":
        n = notas.setdefault(r["motivo"], len(notas) + 1)
        texto = "não se aplica" if r["status"] == "nao_se_aplica" else "indisponível"
        return f'<td{classe}><span class="ind" title="{e(r["motivo"])}">{texto}</span><sup>{n}</sup></td>'
    if ind["metrica"] in ("inicio_fim", "variacao_pct"):
        casas_d = 1 if ind["metrica"] == "variacao_pct" else casas
        corpo = (f'<span class="v">{numero(r["valor"], casas_d, sinal=True)} {e(_unidade_variacao(ind))}</span>'
                 f'<span class="pf">{numero(r["valor_inicio"], casas)} → {numero(r["valor_fim"], casas)}</span>'
                 f'<span class="pf">{e(str(r["data_inicio"]))} → {e(str(r["data_fim"]))}</span>')
    else:
        periodo = (f'{r["data_inicio"]} a {r["data_fim"]}' if r["data_inicio"] != r["data_fim"]
                   else str(r["data_inicio"]))
        corpo = (f'<span class="v">{numero(r["valor"], casas)}</span>'
                 f'<span class="pf">{e(periodo)}</span>')
    return f"<td{classe}>{corpo}</td>"


def _cabecalho(periodos: list[Periodo], dados_ate: str) -> str:
    ths = []
    for p in periodos:
        nome = e(p.nome)
        if p.pai:
            ths.append(f'<th class="subp">↳ {nome}</th>')
        elif p.em_curso:
            ths.append(f"<th>{nome}<br><span class=\"un\">em curso</span></th>")
        else:
            ths.append(f"<th>{nome}<br><span class=\"un\">{p.inicio.year}–{p.fim.year}</span></th>")
    return f"<thead><tr><th>Indicador</th>{''.join(ths)}</tr></thead>"


def _notas_html(notas: dict) -> str:
    if not notas:
        return ""
    itens = "".join(f"<li value=\"{n}\">{e(m[0].upper() + m[1:])}.</li>" for m, n in notas.items())
    return f'<ol class="notas">{itens}</ol>'


def tabela(linhas: list[tuple[dict, pd.DataFrame]], periodos: list[Periodo], grupos: bool = False) -> str:
    notas: dict[str, int] = {}
    corpo = []
    secao = None
    for ind, res in linhas:
        if grupos and ind.get("secao") != secao:
            secao = ind.get("secao")
            corpo.append(f'<tr class="grupo"><td colspan="{len(periodos) + 1}">{e(secao)}</td></tr>')
        res = res.set_index("periodo")
        tds = []
        for p in periodos:
            r = res.loc[p.id].copy()
            r["_sub"] = p.pai is not None
            tds.append(celula(r, ind, notas))
        rotulo = (ind.get("_rotulo") or ind["nome"]).replace("ano-base", str(carregar_periodos()["ano_base_deflacao"]))
        corpo.append(f'<tr><td>{e(rotulo)} <span class="un">{e(ind["unidade"])}</span></td>{"".join(tds)}</tr>')
    return (f'<div class="tabela-wrap"><table>{_cabecalho(periodos, "")}<tbody>{"".join(corpo)}'
            f"</tbody></table></div>{_notas_html(notas)}")


# ------------------------------------------------------------------ gráficos
def _pontos_medios(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Posiciona cada observação no meio do seu período de referência."""
    if freq == "diaria":
        return df
    ini = df["data"] if freq != "trimestral_movel" else df["data"] - pd.DateOffset(months=2)
    fim = fim_do_periodo(df["data"], freq)
    return df.assign(data=ini + (fim - ini) / 2)


def figura(gid: str, titulo: str, series: list[dict], unidade: str, casas: int, nota: str,
           mandatos: list[Periodo], subcortes: list, x_fim: pd.Timestamp, quebras=None) -> str:
    svg = grafico_linhas(gid, series, mandatos, subcortes, X_INICIO, x_fim, unidade, casas,
                         titulo=titulo, quebras=quebras, rotulo_data=series[0]["rotulo"])
    return (f'<figure class="figura"><h3>{e(titulo)}</h3><div class="meta">{e(unidade)}</div>{svg}'
            f'<p class="fonte">{nota}</p></figure>')


# ------------------------------------------------------------------ relatório
def _fonte_serie(sid: str, meta: dict) -> str:
    m = meta[sid]
    cadeia = [sid]
    while meta[cadeia[-1]].get("derivada"):
        cadeia.append(meta[cadeia[-1]]["origem"])
    original = meta[cadeia[-1]]
    codigo = ", ".join(f"{k} {v}" for k, v in original["codigo"].items() if k != "classificacoes")
    txt = f"Fonte: {FONTES[m['fonte']]} ({codigo}). Arquivo: <code>data/processed/"
    txt += f"{'derivadas' if m.get('derivada') else 'series'}/{sid}.csv</code>"
    if m.get("derivada"):
        txt += f", calculado a partir de <code>{e(original['id'])}</code>"
    return txt + "."


def _ressalvas(sids: list[str], meta: dict) -> list[str]:
    vistas, saida = set(), []
    for sid in sids:
        atual = sid
        while True:
            obs = (meta[atual].get("observacoes") or "").strip()
            if obs and obs not in vistas:
                vistas.add(obs)
                saida.append(f"{meta[atual]['nome']}: {obs}")
            if not meta[atual].get("derivada"):
                break
            atual = meta[atual]["origem"]
    return saida


def gerar_relatorio() -> Path:
    cfg = carregar_indicadores()
    cfg_periodos = carregar_periodos()
    catalogo = carregar_catalogo()
    meta = metadados()
    periodos = listar_periodos()
    mandatos = [p for p in periodos if p.pai is None]
    subcortes = [p.inicio for p in periodos if p.pai and p.inicio != next(m for m in mandatos if m.id == p.pai).inicio]
    resultados = pd.read_csv(ANALISE_DIR / "indicadores_por_periodo.csv", dtype={"data_inicio": str, "data_fim": str})
    pares = pd.read_csv(ANALISE_DIR / "pares_por_mandato.csv", dtype={"data_inicio": str, "data_fim": str})
    coleta = pd.read_csv(PROCESSED_DIR / "coleta_resumo.csv")
    nomes_paises = catalogo["padroes"]["worldbank_nomes"]
    paises = catalogo["padroes"]["worldbank_paises"]
    ano_base = cfg_periodos["ano_base_deflacao"]

    series_cache: dict[str, pd.DataFrame] = {}

    def serie(sid: str) -> pd.DataFrame:
        if sid not in series_cache:
            series_cache[sid] = ler_serie(sid)
        return series_cache[sid]

    x_fim = max(fim_do_periodo(serie(i["serie"])["data"], meta[i["serie"]]["frequencia"]).max()
                for i in cfg["indicadores"])

    def rotulo(freq):
        return lambda t: _fmt_data(t, freq)

    # ---- quadro geral
    linhas = [(i, resultados[resultados["indicador"] == i["id"]]) for i in cfg["indicadores"]]
    secoes: dict[str, list[dict]] = {}
    for i in cfg["indicadores"]:
        secoes.setdefault(i["secao"], []).append(i)

    blocos = []
    for n, (secao, inds) in enumerate(secoes.items(), start=1):
        sid_sec = f"sec{n}"
        partes = [f'<h2 id="{sid_sec}">{e(secao)}</h2>']
        partes.append(tabela([(i, resultados[resultados["indicador"] == i["id"]]) for i in inds], periodos))
        metodo = "".join(f"<li><b>{e(i['nome'].replace('ano-base', str(ano_base)))}.</b> {e(i.get('nota', '').strip())}</li>"
                         for i in inds if i.get("nota"))
        if metodo:
            partes.append(f"<h3>Como cada indicador é calculado</h3><ul>{metodo}</ul>")
        graficos = []
        for i in inds:
            g = i.get("grafico", i["serie"])
            if g not in [x[0] for x in graficos]:
                graficos.append((g, i))
        for k, (g, i) in enumerate(graficos):
            m = meta[g]
            df = serie(g)
            if "pais" in df:
                df = df[df["pais"] == i.get("pais", "BRA")]
            freq = m["frequencia"]
            casas = int(i.get("casas", 1)) if g == i["serie"] else 1
            unidade = m["unidade"].replace("ano-base", str(ano_base))
            nota = _fonte_serie(g, meta)
            obs = _ressalvas([g], meta)
            if obs:
                nota += " " + " ".join(e(o) for o in obs)
            partes.append(figura(f"g{n}_{k}", m["nome"], [{
                "nome": "Brasil", "df": _pontos_medios(df, freq), "slot": 1,
                "marcadores": freq == "anual", "rotulo": rotulo(freq)}],
                unidade, casas, nota, mandatos, subcortes, x_fim,
                quebras=[pd.Timestamp(q) for q in i.get("quebra", [])]))
        blocos.append("".join(partes))

    # ---- pares
    partes_pares = ['<h2 id="pares">Comparação com pares (Banco Mundial)</h2>',
                    "<p>Mesma métrica e mesmos anos para Brasil e para os agregados do Banco Mundial. "
                    "Os agregados são calculados pelo próprio Banco Mundial. Como a série do Brasil aqui "
                    "também vem do Banco Mundial, os valores podem diferir um pouco dos das seções acima, "
                    "que usam IBGE e Banco Central.</p>"]
    for k, par in enumerate(cfg["pares"]):
        res = pares[pares["indicador"] == par["id"]]
        linhas_par = []
        for pais in paises:
            ind = {**par, "_rotulo": nomes_paises[pais]}
            linhas_par.append((ind, res[res["pais"] == pais].drop(columns="pais")))
        partes_pares.append(f"<h3>{e(par['nome'])} <span class=\"un\">{e(par['unidade'])}</span></h3>")
        partes_pares.append(tabela(linhas_par, mandatos))
        df = serie(par["serie"])
        m = meta[par["serie"]]
        series_g = [{"nome": nomes_paises[p], "df": _pontos_medios(df[df["pais"] == p][["data", "valor"]], "anual"),
                     "slot": j + 1, "marcadores": False, "rotulo": rotulo("anual")}
                    for j, p in enumerate(paises)]
        nota = _fonte_serie(par["serie"], meta)
        obs = _ressalvas([par["serie"]], meta)
        if obs:
            nota += " " + " ".join(e(o) for o in obs)
        partes_pares.append(figura(f"p{k}", m["nome"], series_g, m["unidade"], int(par.get("casas", 1)),
                                   nota, mandatos, subcortes, x_fim))

    # ---- limitações e rastreabilidade
    usadas = []
    for i in cfg["indicadores"]:
        for s in (i["serie"], i.get("grafico")):
            if s and s not in usadas:
                usadas.append(s)
    ressalvas = "".join(f"<li>{e(r)}</li>" for r in _ressalvas(usadas, meta))
    quebras = "".join(f"<li><b>{e(i['nome'])}</b>: quebra em {', '.join(str(pd.Timestamp(q).year) for q in i['quebra'])}. "
                      f"{e(i.get('nota', '').strip())}</li>" for i in cfg["indicadores"] if i.get("quebra"))

    linhas_rast = []
    for _, c in coleta.iterrows():
        m = meta.get(c["id"], {})
        linhas_rast.append(
            f"<tr><td><code>{e(c['id'])}</code><span class=\"pf\">{e(m.get('nome', ''))}</span></td>"
            f"<td>{e(FONTES.get(c['fonte'], c['fonte']))}</td><td>{e(str(c['codigo']))}</td>"
            f"<td>{e(str(c.get('primeira_data', '')))} a {e(str(c.get('ultima_data', '')))}</td>"
            f"<td>{e(str(c['status']))}</td><td>{e(str(c.get('baixado_em', ''))[:16].replace('T', ' '))}</td></tr>")
    baixado = pd.to_datetime(coleta["baixado_em"].dropna().str[:10])

    notas_periodos = "".join(f"<li><b>{e(p.nome)}.</b> {e(p.nota)}</li>" for p in mandatos if p.nota)
    nav = "".join(f'<a href="#sec{n}">{e(s)}</a>' for n, s in enumerate(secoes, start=1))
    nav += '<a href="#pares">Comparação com pares</a><a href="#limitacoes">Limitações</a><a href="#fontes">Fontes</a>'
    gerado = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")

    pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Economia por mandato</title>
<style>{(AQUI / 'relatorio.css').read_text(encoding='utf-8')}</style>
</head>
<body>
<main>
<h1>Economia por mandato: indicadores do Brasil desde 2003</h1>
<p class="sub">Indicadores oficiais organizados por mandato presidencial, com as mesmas fórmulas para todos os governos.</p>
<p class="meta">Gerado em {gerado} por <code>python -m src.main</code> · dados baixados em
{baixado.min():%d/%m/%Y}{'' if baixado.min() == baixado.max() else f' a {baixado.max():%d/%m/%Y}'} ·
valores em reais a preços médios de {ano_base} (IPCA)</p>
<nav><a href="#leitura">Como ler</a><a href="#quadro">Quadro geral</a>{nav}</nav>

<div class="aviso" id="leitura">
<p><b>Como ler.</b> Cada coluna é um período de config/periodos.yaml. Médias e acumulados usam as
observações que terminam dentro do período. Indicadores de nível (desemprego, dívida, reservas, Gini)
comparam a última observação antes da posse com a última do período: o valor herdado contra o valor
entregue. Abaixo de cada número aparecem os dados usados.</p>
<p><b>Correlação não é causalidade.</b> O relatório descreve o que aconteceu em cada período. Ele não
atribui resultados a governos: choques externos, decisões de mandatos anteriores e o ciclo econômico
afetam todos os números.</p>
<p><b>Mandato em curso.</b> Lula 3 usa só os dados observados até a última divulgação, sem anualizar
nem projetar. Acumulados do mandato em curso cobrem menos tempo e não são comparáveis com os de
mandatos completos.</p>
<p><b>"Indisponível"</b> significa que a série não cobre o período inteiro ou que o cálculo
atravessaria uma quebra metodológica. Nenhum valor é estimado. O motivo aparece na nota numerada.</p>
</div>

<h2 id="quadro">Quadro geral</h2>
{tabela(linhas, periodos, grupos=True)}
<ul class="notas">{notas_periodos}</ul>

{''.join(blocos)}
{''.join(partes_pares)}

<h2 id="limitacoes">Limitações e quebras metodológicas</h2>
<ul>
<li>As faixas cinzas dos gráficos marcam os mandatos. Elas têm a mesma cor para todos os governos e só separam períodos vizinhos.</li>
<li>Valores em dólar (reservas, balança comercial) e o câmbio são nominais e não foram deflacionados.</li>
<li>O rendimento do trabalho é deflacionado pelo IBGE para o trimestre mais recente. O nível da série muda a cada divulgação, mas as variações se mantêm.</li>
<li>Eventos globais, como a crise financeira de 2008–09 e a pandemia de 2020, atingem vários países ao mesmo tempo. A comparação com pares ajuda a ver esse contexto, mas não isola o efeito de políticas. Preços de commodities e juros internacionais não estão incluídos.</li>
<li>As fontes revisam dados passados, principalmente PIB trimestral e Banco Mundial. Uma nova coleta pode mudar números antigos.</li>
<li>Uma observação pertence ao período em que termina. Por convenção, 2016T3 entra em Temer e séries anuais não são divididas em subperíodos de 2016.</li>
{quebras}
</ul>
<h3>Ressalvas das séries usadas</h3>
<ul>{ressalvas}</ul>

<h2 id="fontes">Fontes e rastreabilidade</h2>
<p>Cada série tem a resposta bruta da API em <code>data/raw/&lt;fonte&gt;/&lt;id&gt;.json</code> e os
metadados (URLs, data de download, SHA-256) em <code>&lt;id&gt;.meta.json</code>. Os números das
tabelas estão em <code>data/processed/analise/indicadores_por_periodo.csv</code> e
<code>pares_por_mandato.csv</code>. As regras de cada indicador estão em <code>config/indicadores.yaml</code>.</p>
<div class="tabela-wrap"><table>
<thead><tr><th>Série</th><th>Fonte</th><th>Código</th><th>Cobertura</th><th>Status</th><th>Baixado em</th></tr></thead>
<tbody>{''.join(linhas_rast)}</tbody></table></div>
</main>
<script>{(AQUI / 'relatorio.js').read_text(encoding='utf-8')}</script>
</body>
</html>
"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    destino = REPORTS_DIR / "relatorio.html"
    destino.write_text(pagina, encoding="utf-8")
    log.info("relatório gravado em %s (%d KB)", destino, destino.stat().st_size // 1024)
    return destino
