# Cartão na Mesa

**Árbitros, torcida e placar na distribuição de cartões do Brasileirão Série A (2020–2023)**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![pandas](https://img.shields.io/badge/pandas-3.1.1-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Plotly](https://img.shields.io/badge/Plotly-5.24.1-3F4F75?logo=plotly&logoColor=white)](https://plotly.com/python/)
[![Código: MIT](https://img.shields.io/badge/c%C3%B3digo-MIT-green)](LICENSE)
[![Dados e texto: CC-BY 4.0](https://img.shields.io/badge/dados%20e%20texto-CC--BY%204.0-lightgrey)](LICENSE-DADOS.md)
[![Artigo](https://img.shields.io/badge/artigo-GitHub%20Pages-1e3a8a)](https://natanbraslavsky.github.io/g2-projetopratico/)

| | |
|---|---|
| **Autor** | Natan Pereira Braslavsky, Pedro Duarte Machado |
| **Professor** | Alexandre Neves Louzada |
| **Instituição** | Universidade La Salle |
| **Curso** | Bacharelado em Sistemas de Informação — 6º período |
| **Disciplina** | Linguagem de Programação (Análise e Visualização de Dados com Python) |
| **Semestre** | 2026/2 |
| **Artigo** | <https://natanbraslavsky.github.io/g2-projetopratico/> |
| **Fonte dos dados** | <https://www.kaggle.com/datasets/lucasbral/brasileirao-cartoes-20-23> |

**Palavras-chave:** arbitragem · viés do mandante · futebol brasileiro · análise exploratória de dados · Python · princípios FAIR

---

## Resumo executivo

O projeto analisa as **1.520 partidas** e os **7.921 cartões** do Campeonato Brasileiro Série A de 2020 a 2023 para entender o que explica a variação disciplinar entre os jogos. Um pipeline em Python trata uma base com datas escritas por extenso, público com separador de milhar e cartões guardados como listas JSON, e reconstrói o placar de cada partida minuto a minuto.

| Pergunta de pesquisa | Principal achado |
|---|---|
| **RQ1.** Quanto o volume de cartões varia entre árbitros? | A média vai de 3,5 a 7,1 cartões por jogo (Kruskal–Wallis, p < 0,001). Oito árbitros ficam fora dos limites de controle do gráfico de funil. |
| **RQ2.** A torcida está associada a um viés contra o visitante? | Com portões fechados, a diferença de amarelos foi nula (−0,04). Com público, o visitante recebeu +0,28 amarelo por jogo, chegando a +0,43 em jogos com mais de 35 mil pagantes. |
| **RQ3.** Quando e em que placar os cartões aparecem? | 65% saem no 2º tempo. A maior taxa é a do visitante que vence na etapa final: 4,1 cartões por 90 minutos. |

O artigo completo, com gráficos interativos, está em **<https://natanbraslavsky.github.io/g2-projetopratico/>**.

---

## Estrutura do repositório

```
g2-projetopratico/
├── README.md
├── LICENSE                         licença MIT (código)
├── LICENSE-DADOS.md                licença CC-BY 4.0 (dados derivados e texto)
├── requirements.txt                dependências congeladas com pip freeze
├── .gitignore
├── data/
│   ├── raw/
│   │   └── partidas_20_23.csv      arquivo original do Kaggle, sem alterações
│   ├── processed/
│   │   ├── partidas.parquet        1 linha por partida
│   │   ├── partidas.csv.gz
│   │   ├── eventos.parquet         1 linha por cartão ou gol
│   │   ├── eventos.csv.gz
│   │   └── relatorio_etl.json      contagens de cada etapa do pipeline
│   └── data_dictionary.md          dicionário de variáveis
├── notebooks/
│   └── analise_exploratoria.ipynb  exploração, validação e prototipação
├── src/
│   ├── __init__.py
│   ├── etl.py                      ingestão, limpeza, tipagem e persistência
│   ├── metricas.py                 estatísticas descritivas, testes e agregações
│   └── figuras.py                  gráficos Plotly e tabelas do artigo
└── docs/
    ├── index.html                  artigo acadêmico (GitHub Pages)
    └── assets/
        ├── estilo.css
        ├── figuras.js              especificações dos gráficos interativos
        ├── figuras/                versões estáticas (PNG) dos gráficos
        └── tabelas/                resultados em CSV e JSON
```

---

## Como executar

Requisitos: Python 3.12 ou superior (desenvolvido e testado no 3.13) e `git`.

```bash
git clone https://github.com/NatanBraslavsky/g2-projetopratico.git
cd g2-projetopratico
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No Windows, ative o ambiente com `.venv\Scripts\activate`.

### 1. Pipeline ETL

```bash
python -m src.etl
```

Lê `data/raw/partidas_20_23.csv` e grava as tabelas tratadas e o relatório em `data/processed/`. Se o arquivo bruto não existir, ele é baixado do endpoint público do Kaggle, sem credenciais. Para forçar um novo download:

```bash
python -m src.etl --baixar
```

### 2. Figuras e tabelas do artigo

```bash
python -m src.figuras
```

Gera `docs/assets/figuras.js` (gráficos interativos), os PNGs em `docs/assets/figuras/` e as tabelas de resultados em `docs/assets/tabelas/`.

### 3. Notebook

```bash
jupyter notebook notebooks/analise_exploratoria.ipynb
```

### 4. Visualizar o artigo localmente

```bash
python -m http.server 8000 --directory docs
```

Depois, abra <http://localhost:8000>.

---

## Pipeline de dados

| Etapa | Tratamento |
|---|---|
| Leitura | CSV lido inteiramente como texto (`dtype=str`); checagem das 17 colunas esperadas |
| Público | `"12.089"` → `12089.0`; `"No data"` → `NaN`, sem imputação |
| Datas | `"25 de fevereiro de 2021 21:30"` → `datetime64` |
| Temporada | Extraída da URL da fonte, porque a temporada 2020 terminou em 2021 |
| Eventos | Listas JSON de cartões e gols desaninhadas em uma tabela de eventos |
| Minutos | `"90+3'"` → minuto 90, acréscimo 3, chave de ordenação 90,03 |
| Placar momentâneo | Soma acumulada dos gols antes de cada cartão |
| Condição de público | `com_publico`, `portoes_fechados` (sem registro em 2020–2021) ou `desconhecido` |
| Validação | Placar oficial × lista de gols (0 divergências), 380 jogos por temporada, IDs únicos |
| Persistência | Parquet (snappy) e CSV gzip, mais o relatório JSON de rastreabilidade |

Nenhuma linha é descartada sem registro: duplicatas e linhas inválidas são contadas e identificadas em `relatorio_etl.json`.

---

## Princípios FAIR

- **Findable:** README com resumo, palavras-chave, autoria e link para a fonte; metadados `citation_*` no artigo.
- **Accessible:** repositório e artigo públicos; ingestão sem autenticação.
- **Interoperable:** Parquet e CSV gzip; dicionário de dados em Markdown; resultados em CSV e JSON.
- **Reusable:** MIT para o código, CC-BY 4.0 para dados derivados e texto; dependências congeladas; semente fixa (42) nas reamostragens.

---

## Licença e citação

Código sob [MIT](LICENSE). Dados derivados, figuras e texto sob [CC-BY 4.0](LICENSE-DADOS.md). Os dados originais são de Lucas Bral (Kaggle), em domínio público (CC0).

> BRASLAVSKY, Natan. **Cartão na Mesa**: árbitros, torcida e placar na distribuição de cartões do Brasileirão Série A (2020–2023). Universidade La Salle, 2026. Disponível em: <https://natanbraslavsky.github.io/g2-projetopratico/>.
