from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from src import metricas as m
from src.etl import ROOT, carregar_processados

ASSETS = ROOT / "docs" / "assets"
DIR_FIGURAS = ASSETS / "figuras"
DIR_TABELAS = ASSETS / "tabelas"

AZUL = "#2a78d6"
LARANJA = "#eb6834"
AMARELO = "#eda100"
VERMELHO = "#e34948"
CINZA = "#898781"
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"
SUPERFICIE = "#fcfcfb"

FONTE = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"

ROTULO_LADO = {"mandante": "Mandante", "visitante": "Visitante"}
ROTULO_SITUACAO = {"perdendo": "Perdendo", "empatando": "Empatando", "vencendo": "Vencendo"}


def aplicar_tema(fig: go.Figure, altura: int = 440) -> go.Figure:
    fig.update_layout(
        height=altura,
        font=dict(family=FONTE, size=13, color=TINTA_SECUNDARIA),
        paper_bgcolor=SUPERFICIE,
        plot_bgcolor=SUPERFICIE,
        margin=dict(l=64, r=24, t=84, b=64),
        hoverlabel=dict(bgcolor="white", bordercolor=EIXO, font=dict(family=FONTE, color=TINTA)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
        bargap=0.25,
        separators=",.",
    )
    fig.update_xaxes(showgrid=False, linecolor=EIXO, ticks="outside", tickcolor=EIXO, zeroline=False)
    fig.update_yaxes(gridcolor=GRADE, linecolor=EIXO, zeroline=False)
    return fig


def fig_distribuicao_cartoes(partidas: pd.DataFrame) -> go.Figure:
    contagem = partidas["cartoes_total"].value_counts().sort_index()
    valores = np.arange(0, contagem.index.max() + 1)
    observado = contagem.reindex(valores, fill_value=0)
    media = partidas["cartoes_total"].mean()
    esperado = stats.poisson.pmf(valores, media) * len(partidas)
    fig = go.Figure()
    fig.add_bar(
        x=valores,
        y=observado.values,
        name="Observado",
        marker=dict(color=AZUL, cornerradius=4),
        hovertemplate="%{x} cartões<br>%{y} partidas<extra>Observado</extra>",
    )
    fig.add_scatter(
        x=valores,
        y=esperado,
        name=f"Poisson (λ = {media:.2f})".replace(".", ","),
        mode="lines+markers",
        line=dict(color=LARANJA, width=2),
        marker=dict(size=8, color=LARANJA, line=dict(color=SUPERFICIE, width=2)),
        hovertemplate="%{x} cartões<br>%{y:.1f} partidas esperadas<extra>Poisson</extra>",
    )
    fig.update_xaxes(title_text="Cartões na partida (amarelos + vermelhos diretos)", dtick=1)
    fig.update_yaxes(title_text="Número de partidas")
    return aplicar_tema(fig)


def fig_funil_arbitros(partidas: pd.DataFrame) -> go.Figure:
    perfil = m.perfil_arbitros(partidas)
    media = partidas["cartoes_total"].mean()
    n = np.linspace(1, perfil["jogos"].max() + 5, 200)
    ep = np.sqrt(media / n)
    fig = go.Figure()
    for z, nome, traco in [(3.09, "Limite 99,8%", "dash"), (1.96, "Limite 95%", "dot")]:
        fig.add_scatter(x=n, y=media + z * ep, mode="lines", line=dict(color=CINZA, width=1.5, dash=traco), name=nome, hoverinfo="skip")
        fig.add_scatter(x=n, y=media - z * ep, mode="lines", line=dict(color=CINZA, width=1.5, dash=traco), showlegend=False, hoverinfo="skip")
    fig.add_hline(y=media, line=dict(color=TINTA_SECUNDARIA, width=1), annotation_text=f"Média da liga: {media:.2f}".replace(".", ","), annotation_position="top right")
    grupos = [
        ("dentro_do_esperado", "Dentro do esperado", "#b5b3ab"),
        ("acima_do_esperado", "Acima do esperado", LARANJA),
        ("abaixo_do_esperado", "Abaixo do esperado", AZUL),
    ]
    for chave, rotulo, cor in grupos:
        sub = perfil[perfil["classificacao"] == chave]
        fig.add_scatter(
            x=sub["jogos"],
            y=sub["cartoes_por_jogo"],
            mode="markers+text" if chave != "dentro_do_esperado" else "markers",
            text=sub["arbitro"].astype(str).str.split().str[0] + " " + sub["arbitro"].astype(str).str.split().str[-1],
            textposition="middle right",
            textfont=dict(size=11, color=TINTA_SECUNDARIA),
            marker=dict(size=10, color=cor, line=dict(color=SUPERFICIE, width=2)),
            name=rotulo,
            customdata=np.stack([sub["arbitro"].astype(str), sub["expulsoes_por_jogo"]], axis=1),
            hovertemplate="<b>%{customdata[0]}</b><br>%{x} jogos<br>%{y:.2f} cartões/jogo<br>%{customdata[1]:.2f} expulsões/jogo<extra></extra>",
        )
    fig.update_xaxes(title_text="Partidas apitadas (2020–2023)", range=[0, perfil["jogos"].max() + 15])
    fig.update_yaxes(title_text="Cartões por partida", range=[0, 11])
    return aplicar_tema(fig, 500)


def fig_correlacao(partidas: pd.DataFrame) -> go.Figure:
    base = partidas.assign(gols_total=partidas["gols_mandante"].astype(float) + partidas["gols_visitante"].astype(float))
    colunas = {
        "publico": "Público",
        "gols_total": "Gols",
        "saldo_gols": "Saldo do mandante",
        "amarelos_mandante": "Amarelos mandante",
        "amarelos_visitante": "Amarelos visitante",
        "expulsoes_total": "Expulsões",
        "cartoes_total": "Cartões total",
    }
    matriz = base[list(colunas)].astype(float).corr(method="spearman")
    rotulos = list(colunas.values())
    escala = [
        [0.0, "#184f95"],
        [0.25, "#6da7ec"],
        [0.5, "#f0efec"],
        [0.75, "#ee8a88"],
        [1.0, "#b8302f"],
    ]
    mascara = np.triu(np.ones_like(matriz, dtype=bool), k=1)
    z = matriz.to_numpy().copy()
    z[mascara] = np.nan
    texto = np.where(mascara, "", np.vectorize(lambda v: f"{v:.2f}".replace(".", ","))(matriz.to_numpy()))
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=rotulos,
            y=rotulos,
            zmin=-1,
            zmax=1,
            colorscale=escala,
            text=texto,
            texttemplate="%{text}",
            textfont=dict(size=12, color=TINTA),
            xgap=2,
            ygap=2,
            colorbar=dict(title="ρ", thickness=12, outlinewidth=0),
            hovertemplate="%{y} × %{x}<br>ρ de Spearman = %{z:.3f}<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(tickangle=-30)
    return aplicar_tema(fig, 520)


def fig_temporadas(partidas: pd.DataFrame) -> go.Figure:
    tabela = m.cartoes_por_temporada(partidas)
    rotulos = [
        f"{int(t)}<br><span style='font-size:11px'>{f:.0%} portões fechados</span>"
        for t, f in zip(tabela["temporada"], tabela["fracao_portoes_fechados"])
    ]
    fig = go.Figure()
    for coluna, nome, cor in [("amarelos_mandante", "Mandante", AZUL), ("amarelos_visitante", "Visitante", LARANJA)]:
        fig.add_bar(
            x=rotulos,
            y=tabela[coluna],
            name=nome,
            marker=dict(color=cor, cornerradius=4),
            text=tabela[coluna].map(lambda v: f"{v:.2f}".replace(".", ",")),
            textposition="outside",
            textfont=dict(color=TINTA_SECUNDARIA),
            hovertemplate="%{y:.2f} amarelos por jogo<extra>" + nome + "</extra>",
        )
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(title_text="Cartões amarelos por partida", range=[0, 3.3])
    return aplicar_tema(fig)


def fig_faixa_publico(partidas: pd.DataFrame) -> go.Figure:
    tabela = m.vies_por_faixa_publico(partidas)
    cores = [CINZA] + [AZUL] * (len(tabela) - 1)
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=EIXO, width=1.5))
    fig.add_scatter(
        x=tabela["faixa_publico"].astype(str),
        y=tabela["dif_media"],
        mode="markers",
        marker=dict(size=12, color=cores, line=dict(color=SUPERFICIE, width=2)),
        error_y=dict(
            type="data",
            symmetric=False,
            array=tabela["ic95_sup"] - tabela["dif_media"],
            arrayminus=tabela["dif_media"] - tabela["ic95_inf"],
            color=TINTA_SECUNDARIA,
            thickness=1.5,
            width=6,
        ),
        customdata=np.stack([tabela["partidas"], tabela["ic95_inf"], tabela["ic95_sup"]], axis=1),
        hovertemplate="<b>%{x}</b><br>Diferença média: %{y:+.2f}<br>IC 95%: [%{customdata[1]:+.2f}; %{customdata[2]:+.2f}]<br>%{customdata[0]} partidas<extra></extra>",
        showlegend=False,
    )
    fig.update_xaxes(title_text="Público pagante na partida")
    fig.update_yaxes(title_text="Amarelos visitante − amarelos mandante", zeroline=False)
    return aplicar_tema(fig)


def fig_minutos(eventos: pd.DataFrame) -> go.Figure:
    tabela = m.distribuicao_minutos(eventos)
    tabela["expulsoes"] = tabela["segundo_amarelo"] + tabela["vermelho"]
    fig = go.Figure()
    for coluna, nome, cor in [("amarelo", "Amarelos", AMARELO), ("expulsoes", "Expulsões (vermelho direto ou 2º amarelo)", VERMELHO)]:
        fig.add_bar(
            x=tabela["faixa"],
            y=tabela[coluna],
            name=nome,
            marker=dict(color=cor, line=dict(color=SUPERFICIE, width=2)),
            hovertemplate="%{x}<br>%{y} " + nome.split(" ")[0].lower() + "<extra></extra>",
        )
    fig.update_layout(barmode="stack", legend=dict(traceorder="normal"))
    fig.add_vrect(x0=3.5, x1=7.5, fillcolor=GRADE, opacity=0.35, line_width=0, layer="below", annotation_text="2º tempo", annotation_position="top right")
    fig.update_xaxes(title_text="Faixa de minutos")
    fig.update_yaxes(title_text="Cartões (2020–2023)")
    return aplicar_tema(fig)


def fig_taxa_situacao(partidas: pd.DataFrame, eventos: pd.DataFrame) -> go.Figure:
    tabela = m.taxa_cartoes_por_situacao(partidas, eventos, ("tempo", "lado"))
    fig = make_subplots(rows=1, cols=2, subplot_titles=("1º tempo", "2º tempo"), shared_yaxes=True, horizontal_spacing=0.06)
    for coluna, tempo in enumerate([1, 2], start=1):
        for lado, cor in [("mandante", AZUL), ("visitante", LARANJA)]:
            sub = tabela[(tabela["tempo"] == tempo) & (tabela["lado"] == lado)]
            fig.add_bar(
                row=1,
                col=coluna,
                x=sub["situacao_placar"].map(ROTULO_SITUACAO),
                y=sub["cartoes_por_90"],
                name=ROTULO_LADO[lado],
                marker=dict(color=cor, cornerradius=4),
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=sub["ic95_sup"] - sub["cartoes_por_90"],
                    arrayminus=sub["cartoes_por_90"] - sub["ic95_inf"],
                    color=TINTA_SECUNDARIA,
                    thickness=1.2,
                    width=4,
                ),
                customdata=np.stack([sub["cartoes"], sub["minutos"]], axis=1),
                hovertemplate="%{x}<br>%{y:.2f} cartões por 90 min<br>%{customdata[0]:.0f} cartões em %{customdata[1]:,.0f} min<extra>" + ROTULO_LADO[lado] + "</extra>",
                showlegend=coluna == 1,
                legendgroup=lado,
            )
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(title_text="Cartões por 90 minutos de exposição", row=1, col=1)
    fig.update_xaxes(title_text="Placar do time punido")
    fig.update_layout(margin=dict(t=96))
    aplicar_tema(fig, 460)
    fig.update_annotations(font=dict(size=13, color=TINTA))
    return fig


def exportar_tabelas(partidas: pd.DataFrame, eventos: pd.DataFrame) -> dict:
    DIR_TABELAS.mkdir(parents=True, exist_ok=True)
    tabelas = {
        "perfil_arbitros": m.perfil_arbitros(partidas),
        "vies_por_torcida": m.vies_mandante_por_torcida(partidas),
        "vies_por_faixa_publico": m.vies_por_faixa_publico(partidas),
        "cartoes_por_temporada": m.cartoes_por_temporada(partidas),
        "distribuicao_minutos": m.distribuicao_minutos(eventos),
        "taxa_por_situacao": m.taxa_cartoes_por_situacao(partidas, eventos, ("tempo", "lado")),
    }
    for nome, tabela in tabelas.items():
        tabela.round(4).to_csv(DIR_TABELAS / f"{nome}.csv", index=False, encoding="utf-8")

    taxas = m.taxa_cartoes_por_situacao(partidas, eventos, ("tempo",))
    resultados = {
        "descritivo_cartoes": m.resumo_descritivo(partidas["cartoes_total"]),
        "outliers_cartoes": int(m.outliers_iqr(partidas["cartoes_total"]).sum()),
        "kruskal_arbitros": m.teste_diferenca_arbitros(partidas),
        "teste_vies_torcida": m.teste_vies_torcida(partidas),
        "correlacao_publico_vies": m.correlacao_publico_vies(partidas),
        "momento_cartoes": m.concentracao_segundo_tempo(eventos),
        "qui2_situacao_1t": m.teste_taxas_situacao(taxas[taxas["tempo"] == 1]),
        "qui2_situacao_2t": m.teste_taxas_situacao(taxas[taxas["tempo"] == 2]),
    }
    convertido = json.loads(json.dumps(resultados, default=lambda v: v.item() if hasattr(v, "item") else str(v)))
    (DIR_TABELAS / "resultados_estatisticos.json").write_text(
        json.dumps(convertido, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return convertido


def gerar_figuras(exportar_png: bool = True) -> dict[str, go.Figure]:
    partidas, eventos = carregar_processados()
    figuras = {
        "fig-distribuicao": fig_distribuicao_cartoes(partidas),
        "fig-correlacao": fig_correlacao(partidas),
        "fig-arbitros": fig_funil_arbitros(partidas),
        "fig-temporadas": fig_temporadas(partidas),
        "fig-publico": fig_faixa_publico(partidas),
        "fig-minutos": fig_minutos(eventos),
        "fig-situacao": fig_taxa_situacao(partidas, eventos),
    }
    DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    especificacoes = {}
    for nome, fig in figuras.items():
        especificacoes[nome] = json.loads(fig.to_json())
        if exportar_png:
            fig.write_image(DIR_FIGURAS / f"{nome}.png", width=1100, height=fig.layout.height, scale=2)
    conteudo = "window.FIGURAS = " + json.dumps(especificacoes, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (ASSETS / "figuras.js").write_text(conteudo, encoding="utf-8")
    exportar_tabelas(partidas, eventos)
    return figuras


if __name__ == "__main__":
    gerar_figuras()
    print(f"figuras e tabelas salvas em {ASSETS.relative_to(ROOT)}/")
