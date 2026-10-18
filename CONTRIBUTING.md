# Como contribuir

Obrigado pelo interesse. Este projeto compara indicadores econômicos do Brasil por mandato
presidencial com dados oficiais. A regra que vale para qualquer contribuição: **o objetivo é
informar o debate, não defender governo nenhum.** As regras completas estão em
[CLAUDE.md](CLAUDE.md); este guia resume o que elas significam na prática.

## O que é bem-vindo

- **Correções**: erro de cálculo, série com código errado, data de mandato, bug no relatório.
- **Novas séries** de fontes oficiais que ampliem a cobertura (por exemplo, dados anteriores a 2012
  para trabalho e renda).
- **Novos indicadores**, desde que propostos do jeito descrito abaixo.
- **Ressalvas metodológicas**: quebras, revisões ou limitações que o relatório ainda não registra.
- **Relatório**: legibilidade, acessibilidade, explicações de método.

## O que não é aceito

- Adjetivos políticos ou conclusões do tipo "o governo X foi melhor/pior".
- Frases que atribuem causalidade ("a política Y causou Z"). O relatório descreve, não explica.
- Indicadores escolhidos ou retirados depois de ver quem fica bem ou mal na comparação.
- Valores digitados à mão, lembrados de memória ou estimados para preencher lacunas.
- Previsões ou anualização do mandato em curso.
- Séries com quebra metodológica emendadas numa só.

## Propondo um indicador novo

Para manter a neutralidade, **abra uma issue antes do pull request** com:

1. o que o indicador mede e por que ele é relevante para avaliar qualquer governo;
2. a série oficial (fonte, código na API, cobertura);
3. a métrica (`media`, `media_geometrica`, `acumulado`, `inicio_fim` ou `variacao_pct`) e por que
   ela é a adequada.

A discussão deve acontecer **sem olhar os resultados por mandato**. A justificativa precisa valer
para qualquer governo; "este indicador mostra que o mandato X..." não é justificativa. Aprovada a
proposta, o indicador entra em `config/indicadores.yaml` e é aplicado igual a todos os períodos.

## Ambiente

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/macOS
pip install -e ".[dev]"
pytest
```

## Onde mexer

| Para… | Edite |
|---|---|
| Incluir uma série | `config/series.yaml`, com o código confirmado na API e `confirmado_em` |
| Incluir um indicador ou derivada | `config/indicadores.yaml` |
| Mudar datas de mandato ou ano-base | `config/periodos.yaml` |
| Uma fonte nova | um módulo em `src/coleta/` com `baixar` (rede) e `parsear` (função pura) |
| Métricas e regras de cobertura | `src/analise/` |
| Relatório | `src/visualizacao/` |

Nenhum código de série ou data de mandato fica fixo no Python: tudo vem de `config/`.

## Regras para os dados

- **Nunca edite à mão** arquivos em `data/raw/`. A coleta confere o SHA-256 e para se o bruto mudar.
- Para atualizar dados, rode `python -m src.main coleta --forcar` (ou `--series <ids>`) e confira o
  que mudou com `git diff data/`. As fontes revisam dados passados; mudanças em valores antigos são
  esperadas e devem ser mencionadas no pull request.
- Dado que não existe aparece como "indisponível", com o motivo. Não preencha lacunas.

## Antes de abrir o pull request

1. `pytest` passando. Mudança de regra de cálculo vem com teste usando um caso simples calculado
   à mão (veja `tests/test_analise.py`).
2. `python -m src.main` rodando do início ao fim.
3. Se a mudança afeta números, faça commit também de `data/processed/` e `reports/relatorio.html`
   regenerados, para que a revisão mostre o efeito.
4. Na descrição, diga o que mudou e quais números do relatório mudaram por causa disso.

O site em https://feliperamiresterrazas.github.io/economia-mandatos/ é republicado
automaticamente quando o relatório muda no `master`.

## Licença

Ao contribuir, você concorda que o código enviado fica sob a licença MIT ([LICENSE](LICENSE)) e o
conteúdo (textos, relatório, tabelas calculadas) sob CC BY 4.0 ([LICENSE-CONTEUDO.md](LICENSE-CONTEUDO.md)).
