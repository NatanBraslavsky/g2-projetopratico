from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

SEMENTE = 42
MINIMO_JOGOS_ARBITRO = 20
DURACAO_PADRAO = 90


def resumo_descritivo(serie: pd.Series) -> dict:
    q1, q3 = serie.quantile([0.25, 0.75])
    media = serie.mean()
    return {
        "n": int(serie.count()),
        "media": media,
        "mediana": serie.median(),
        "desvio_padrao": serie.std(),
        "variancia": serie.var(),
        "coef_variacao": serie.std() / media if media else np.nan,
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "minimo": serie.min(),
        "maximo": serie.max(),
        "assimetria": serie.skew(),
        "indice_dispersao": serie.var() / media if media else np.nan,
    }


def outliers_iqr(serie: pd.Series, fator: float = 1.5) -> pd.Series:
    q1, q3 = serie.quantile([0.25, 0.75])
    iqr = q3 - q1
    return (serie < q1 - fator * iqr) | (serie > q3 + fator * iqr)


def intervalo_bootstrap(
    valores: np.ndarray,
    estatistica=np.mean,
    reamostragens: int = 10_000,
    confianca: float = 0.95,
    semente: int = SEMENTE,
) -> tuple[float, float]:
    gerador = np.random.default_rng(semente)
    valores = np.asarray(valores)
    amostras = gerador.choice(valores, size=(reamostragens, len(valores)), replace=True)
    resultados = estatistica(amostras, axis=1)
    alfa = (1 - confianca) / 2
    return float(np.quantile(resultados, alfa)), float(np.quantile(resultados, 1 - alfa))


def perfil_arbitros(partidas: pd.DataFrame, minimo_jogos: int = MINIMO_JOGOS_ARBITRO) -> pd.DataFrame:
    media_geral = partidas["cartoes_total"].mean()
    perfil = (
        partidas.groupby("arbitro", observed=True)
        .agg(
            jogos=("partida_id", "count"),
            cartoes_total=("cartoes_total", "sum"),
            cartoes_por_jogo=("cartoes_total", "mean"),
            amarelos_por_jogo=("amarelos_total", "mean"),
            expulsoes_por_jogo=("expulsoes_total", "mean"),
            desvio_padrao=("cartoes_total", "std"),
            dif_vis_mand=("dif_amarelos_vis_mand", "mean"),
        )
        .reset_index()
    )
    erro_padrao = np.sqrt(media_geral / perfil["jogos"])
    perfil["limite_inf_95"] = media_geral - 1.96 * erro_padrao
    perfil["limite_sup_95"] = media_geral + 1.96 * erro_padrao
    perfil["limite_inf_998"] = media_geral - 3.09 * erro_padrao
    perfil["limite_sup_998"] = media_geral + 3.09 * erro_padrao
    perfil["classificacao"] = np.select(
        [
            perfil["cartoes_por_jogo"] > perfil["limite_sup_998"],
            perfil["cartoes_por_jogo"] < perfil["limite_inf_998"],
        ],
        ["acima_do_esperado", "abaixo_do_esperado"],
        default="dentro_do_esperado",
    )
    perfil["elegivel"] = perfil["jogos"] >= minimo_jogos
    return perfil.sort_values("cartoes_por_jogo", ascending=False).reset_index(drop=True)


def teste_diferenca_arbitros(partidas: pd.DataFrame, minimo_jogos: int = MINIMO_JOGOS_ARBITRO) -> dict:
    contagem = partidas["arbitro"].value_counts()
    elegiveis = contagem[contagem >= minimo_jogos].index
    grupos = [
        partidas.loc[partidas["arbitro"] == arbitro, "cartoes_total"].to_numpy()
        for arbitro in elegiveis
    ]
    h, p = stats.kruskal(*grupos)
    n = sum(len(g) for g in grupos)
    k = len(grupos)
    epsilon2 = (h - k + 1) / (n - k)
    return {"arbitros": k, "partidas": n, "H": h, "p_valor": p, "epsilon2": epsilon2}


def vies_mandante_por_torcida(partidas: pd.DataFrame) -> pd.DataFrame:
    base = partidas[partidas["torcida"].isin(["portoes_fechados", "com_publico"])]
    linhas = []
    for condicao, grupo in base.groupby("torcida", observed=True):
        dif = grupo["dif_amarelos_vis_mand"].to_numpy()
        inf, sup = intervalo_bootstrap(dif)
        linhas.append(
            {
                "torcida": condicao,
                "partidas": len(grupo),
                "amarelos_mandante": grupo["amarelos_mandante"].mean(),
                "amarelos_visitante": grupo["amarelos_visitante"].mean(),
                "dif_media": dif.mean(),
                "ic95_inf": inf,
                "ic95_sup": sup,
                "expulsoes_mandante": grupo["expulsoes_mandante"].mean(),
                "expulsoes_visitante": grupo["expulsoes_visitante"].mean(),
                "vitorias_mandante": (grupo["resultado"] == "vitoria_mandante").mean(),
                "empates": (grupo["resultado"] == "empate").mean(),
                "vitorias_visitante": (grupo["resultado"] == "vitoria_visitante").mean(),
                "saldo_gols_mandante": grupo["saldo_gols"].astype(float).mean(),
            }
        )
    return pd.DataFrame(linhas)


def teste_vies_torcida(partidas: pd.DataFrame) -> dict:
    fechados = partidas.loc[partidas["torcida"] == "portoes_fechados", "dif_amarelos_vis_mand"]
    publico = partidas.loc[partidas["torcida"] == "com_publico", "dif_amarelos_vis_mand"]
    u, p_mw = stats.mannwhitneyu(publico, fechados, alternative="two-sided")
    t_f, p_f = stats.wilcoxon(fechados[fechados != 0])
    t_p, p_p = stats.wilcoxon(publico[publico != 0])
    diferenca = publico.mean() - fechados.mean()
    gerador = np.random.default_rng(SEMENTE)
    a, b = publico.to_numpy(), fechados.to_numpy()
    boot = np.array(
        [
            gerador.choice(a, len(a)).mean() - gerador.choice(b, len(b)).mean()
            for _ in range(10_000)
        ]
    )
    return {
        "diferenca_das_medias": diferenca,
        "ic95_inf": float(np.quantile(boot, 0.025)),
        "ic95_sup": float(np.quantile(boot, 0.975)),
        "mann_whitney_U": u,
        "p_valor_mann_whitney": p_mw,
        "p_valor_wilcoxon_fechados": p_f,
        "p_valor_wilcoxon_publico": p_p,
    }


def correlacao_publico_vies(partidas: pd.DataFrame) -> dict:
    base = partidas.dropna(subset=["publico"])
    rho, p = stats.spearmanr(base["publico"], base["dif_amarelos_vis_mand"])
    return {"partidas": len(base), "rho_spearman": rho, "p_valor": p}


def vies_por_faixa_publico(partidas: pd.DataFrame) -> pd.DataFrame:
    base = partidas.copy()
    faixas = [-1, 0, 10_000, 20_000, 35_000, np.inf]
    rotulos = ["Portões fechados", "Até 10 mil", "10 a 20 mil", "20 a 35 mil", "Acima de 35 mil"]
    publico = base["publico"].where(base["torcida"] != "portoes_fechados", 0)
    base["faixa_publico"] = pd.cut(publico, bins=faixas, labels=rotulos)
    base = base.dropna(subset=["faixa_publico"])
    linhas = []
    for faixa, grupo in base.groupby("faixa_publico", observed=True):
        inf, sup = intervalo_bootstrap(grupo["dif_amarelos_vis_mand"].to_numpy())
        linhas.append(
            {
                "faixa_publico": faixa,
                "partidas": len(grupo),
                "dif_media": grupo["dif_amarelos_vis_mand"].mean(),
                "ic95_inf": inf,
                "ic95_sup": sup,
            }
        )
    return pd.DataFrame(linhas)


def cartoes_por_temporada(partidas: pd.DataFrame) -> pd.DataFrame:
    base = partidas.assign(
        gols_total=partidas["gols_mandante"].astype(float) + partidas["gols_visitante"].astype(float),
        fechado=(partidas["torcida"] == "portoes_fechados").astype(float),
    )
    return (
        base.groupby("temporada", observed=True)
        .agg(
            partidas=("partida_id", "count"),
            cartoes_por_jogo=("cartoes_total", "mean"),
            amarelos_mandante=("amarelos_mandante", "mean"),
            amarelos_visitante=("amarelos_visitante", "mean"),
            expulsoes_por_jogo=("expulsoes_total", "mean"),
            gols_por_jogo=("gols_total", "mean"),
            fracao_portoes_fechados=("fechado", "mean"),
        )
        .reset_index()
    )


def distribuicao_minutos(eventos: pd.DataFrame, largura: int = 15) -> pd.DataFrame:
    cartoes = eventos[eventos["tipo"] != "gol"].copy()
    rotulos = {}
    inicio = 0
    while inicio < DURACAO_PADRAO:
        fim = inicio + largura
        rotulos[(inicio, fim)] = f"{inicio + 1}–{fim}"
        inicio = fim
    def faixa(linha):
        if linha["acrescimo"] > 0:
            return "45+ (acréscimos)" if linha["tempo"] == 1 else "90+ (acréscimos)"
        for (a, b), rotulo in rotulos.items():
            if a < linha["minuto_base"] <= b:
                return rotulo
        return rotulos[(0, largura)]
    cartoes["faixa"] = cartoes.apply(faixa, axis=1)
    ordem = []
    for (a, b), rotulo in rotulos.items():
        ordem.append(rotulo)
        if b == 45:
            ordem.append("45+ (acréscimos)")
    ordem.append("90+ (acréscimos)")
    tabela = (
        cartoes.groupby(["faixa", "tipo"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reindex(ordem, fill_value=0)
    )
    tabela.index.name = "faixa"
    return tabela.reset_index()


def tempo_por_situacao(partidas: pd.DataFrame, eventos: pd.DataFrame) -> pd.DataFrame:
    gols = eventos[eventos["tipo"] == "gol"]
    fim_por_partida = eventos.groupby("partida_id")["minuto_ordenacao"].max().clip(lower=DURACAO_PADRAO)
    gols_por_partida = {pid: g.sort_values("minuto_ordenacao") for pid, g in gols.groupby("partida_id")}
    intervalo_tempos = {1: (0.0, 46.0), 2: (46.0, np.inf)}
    linhas = []
    for partida_id in partidas["partida_id"]:
        g = gols_por_partida.get(partida_id, gols.iloc[0:0])
        fim = float(fim_por_partida.get(partida_id, DURACAO_PADRAO))
        marcos = [0.0] + g["minuto_ordenacao"].tolist() + [fim]
        lados = g["lado"].tolist()
        placar_m = placar_v = 0
        for i in range(len(marcos) - 1):
            saldo = placar_m - placar_v
            for tempo, (a, b) in intervalo_tempos.items():
                duracao = max(min(marcos[i + 1], b) - max(marcos[i], a), 0.0)
                if duracao == 0:
                    continue
                for lado, s in (("mandante", saldo), ("visitante", -saldo)):
                    situacao = "vencendo" if s > 0 else "perdendo" if s < 0 else "empatando"
                    linhas.append({"tempo": tempo, "lado": lado, "situacao_placar": situacao, "minutos": duracao})
            if i < len(lados):
                if lados[i] == "mandante":
                    placar_m += 1
                else:
                    placar_v += 1
    return pd.DataFrame(linhas).groupby(["tempo", "lado", "situacao_placar"], as_index=False)["minutos"].sum()


ORDEM_SITUACAO = {"perdendo": 0, "empatando": 1, "vencendo": 2}


def taxa_cartoes_por_situacao(
    partidas: pd.DataFrame, eventos: pd.DataFrame, por: tuple[str, ...] = ("lado",)
) -> pd.DataFrame:
    chaves = list(por) + ["situacao_placar"]
    exposicao = tempo_por_situacao(partidas, eventos).groupby(chaves, as_index=False)["minutos"].sum()
    cartoes = eventos[eventos["tipo"] != "gol"].copy()
    for coluna in ["lado", "situacao_placar"]:
        cartoes[coluna] = cartoes[coluna].astype(str)
    contagem = cartoes.groupby(chaves).size().rename("cartoes").reset_index()
    tabela = exposicao.merge(contagem, on=chaves, how="left").fillna({"cartoes": 0})
    tabela["cartoes_por_90"] = tabela["cartoes"] / tabela["minutos"] * 90
    z = 1.96
    tabela["ic95_inf"] = (tabela["cartoes"] - z * np.sqrt(tabela["cartoes"])) / tabela["minutos"] * 90
    tabela["ic95_sup"] = (tabela["cartoes"] + z * np.sqrt(tabela["cartoes"])) / tabela["minutos"] * 90
    tabela["_ordem"] = tabela["situacao_placar"].map(ORDEM_SITUACAO)
    return tabela.sort_values(list(por) + ["_ordem"]).drop(columns="_ordem").reset_index(drop=True)


def teste_taxas_situacao(tabela: pd.DataFrame) -> dict:
    total = tabela.groupby("situacao_placar")[["cartoes", "minutos"]].sum()
    total = total[total["minutos"] > 0]
    esperado = total["minutos"] / total["minutos"].sum() * total["cartoes"].sum()
    qui2, p = stats.chisquare(total["cartoes"], esperado)
    taxas = total["cartoes"] / total["minutos"] * 90
    return {
        "qui2": qui2,
        "p_valor": p,
        "taxa_perdendo": taxas.get("perdendo"),
        "taxa_empatando": taxas.get("empatando"),
        "taxa_vencendo": taxas.get("vencendo"),
        "razao_perdendo_vencendo": taxas.get("perdendo") / taxas.get("vencendo"),
    }


def concentracao_segundo_tempo(eventos: pd.DataFrame) -> dict:
    cartoes = eventos[eventos["tipo"] != "gol"]
    return {
        "cartoes": len(cartoes),
        "fracao_segundo_tempo": (cartoes["tempo"] == 2).mean(),
        "fracao_acrescimos": cartoes["em_acrescimo"].mean(),
        "minuto_mediano": cartoes["minuto_ordenacao"].median(),
    }
