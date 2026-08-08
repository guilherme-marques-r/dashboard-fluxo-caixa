"""Métricas e correlações do fluxo de caixa.

Funções puras que transformam o DataFrame de lançamentos em indicadores:
composição de custos, % de ração, custo por kg, margem, fluxo temporal etc.
"""
import pandas as pd

# Categorias de capital (capex) — não fazem parte do custo operacional de produção.
CATEGORIAS_NAO_OPERACIONAIS = ("Investimento", "Fábrica Ração")


def eh_entrada(tipo):
    return str(tipo or "").strip().lower().startswith("entrada")


def eh_saida(tipo):
    return str(tipo or "").strip().lower().startswith("saida")


def categorizar(df):
    """Devolve cópia com colunas auxiliares:
    fluxo (sinal), eh_entrada, eh_saida, mes (Aaaa-mm).
    """
    d = df.copy()
    d["eh_entrada"] = d["tipo"].map(eh_entrada)
    d["eh_saida"] = d["tipo"].map(eh_saida)
    d["fluxo"] = d["valor"].where(d["eh_entrada"], -d["valor"])
    d["mes"] = d["data"].dt.to_period("M").astype(str)
    return d


def resumo_geral(df):
    """KPIs gerais: receitas, despesas, resultado e nº de lançamentos."""
    if df.empty:
        return {"receitas": 0.0, "despesas": 0.0, "resultado": 0.0, "lançamentos": 0}
    d = categorizar(df)
    receitas = float(d.loc[d["eh_entrada"], "valor"].sum())
    despesas = float(d.loc[d["eh_saida"], "valor"].sum())
    return {
        "receitas": receitas,
        "despesas": despesas,
        "resultado": receitas - despesas,
        "lançamentos": int(len(df)),
    }


def composicao_despesas(df, nivel="categoria_n1"):
    """Soma das despesas por categoria, com % sobre o total de despesas.

    Retorna DataFrame com colunas: categoria, valor, pct.
    """
    vazia = pd.DataFrame(columns=["categoria", "valor", "pct"])
    if df.empty:
        return vazia
    d = categorizar(df)
    saidas = d[d["eh_saida"]]
    if saidas.empty:
        return vazia
    total = saidas["valor"].sum()
    grupo = saidas.groupby(nivel)["valor"].sum().reset_index()
    grupo.columns = ["categoria", "valor"]
    grupo["pct"] = (grupo["valor"] / total * 100) if total else 0.0
    return grupo.sort_values("valor", ascending=False).reset_index(drop=True)


def racao_sobre_custo(df):
    """% do valor gasto em ração sobre o total de despesas."""
    if df.empty:
        return 0.0
    d = categorizar(df)
    saidas = d.loc[d["eh_saida"]]
    if saidas.empty:
        return 0.0
    total = saidas["valor"].sum()
    racao = saidas.loc[saidas["categoria_n1"] == "Racao", "valor"].sum()
    return (racao / total * 100) if total else 0.0


def racao_por_mes(df):
    """Evolução mensal: custo total, custo de ração e % da ração."""
    vazia = pd.DataFrame(columns=["mes", "custo_total", "racao", "pct_racao"])
    if df.empty:
        return vazia
    d = categorizar(df)
    saidas = d.loc[d["eh_saida"]]
    if saidas.empty:
        return vazia
    custos = saidas.groupby("mes")["valor"].sum().reset_index()
    custos.columns = ["mes", "custo_total"]
    racao = (saidas.loc[saidas["categoria_n1"] == "Racao"]
                   .groupby("mes")["valor"].sum().reset_index())
    racao.columns = ["mes", "racao"]
    res = custos.merge(racao, on="mes", how="left").fillna(0)
    res["pct_racao"] = res["racao"] / res["custo_total"] * 100
    return res.sort_values("mes").reset_index(drop=True)


def fluxo_mensal(df, saldo_inicial=0.0):
    """Receitas, despesas, resultado e caixa acumulado por mês.

    O `saldo_inicial` (célula E1 da planilha) soma-se ao caixa acumulado para
    refletir o caixa real, diferenciando-o do resultado do período.
    """
    vazia = pd.DataFrame(columns=["mes", "receitas", "despesas", "resultado", "saldo"])
    if df.empty:
        return vazia
    d = categorizar(df)
    resumo = (d.groupby("mes")
              .agg(receitas=("valor", lambda x: x[d.loc[x.index, "eh_entrada"]].sum()),
                   despesas=("valor", lambda x: x[d.loc[x.index, "eh_saida"]].sum()))
              .reset_index())
    resumo["resultado"] = resumo["receitas"] - resumo["despesas"]
    resumo["saldo"] = resumo["resultado"].cumsum() + saldo_inicial
    return resumo.sort_values("mes").reset_index(drop=True)


def despesas_operacionais(df):
    """Total de despesas operacionais (exclui Investimento e Fábrica Ração)."""
    if df.empty:
        return 0.0
    d = categorizar(df)
    saidas = d.loc[d["eh_saida"]]
    if saidas.empty:
        return 0.0
    return float(saidas.loc[~saidas["categoria_n1"].isin(CATEGORIAS_NAO_OPERACIONAIS),
                            "valor"].sum())


def capex_total(df):
    """Total de despesas de capital (Investimento + Fábrica Ração)."""
    if df.empty:
        return 0.0
    d = categorizar(df)
    saidas = d.loc[d["eh_saida"]]
    if saidas.empty:
        return 0.0
    return float(saidas.loc[saidas["categoria_n1"].isin(CATEGORIAS_NAO_OPERACIONAIS),
                            "valor"].sum())


def composicao_capex(df):
    """Composição do custo: operacional × capex (Investimento + Fábrica Ração).

    Retorna DataFrame com colunas: categoria, valor, pct.
    """
    vazia = pd.DataFrame(columns=["categoria", "valor", "pct"])
    if df.empty:
        return vazia
    op = despesas_operacionais(df)
    cap = capex_total(df)
    total = op + cap
    if total <= 0:
        return vazia
    return pd.DataFrame([
        {"categoria": "Custo operacional", "valor": op, "pct": op / total * 100},
        {"categoria": "Investimento + Fábrica Ração", "valor": cap, "pct": cap / total * 100},
    ])


def custo_operacional_por_mes(df):
    """Despesas mensais: totais e operacionais (sem capex).

    Retorna DataFrame com colunas: mes, despesas, despesas_operacionais.
    """
    vazia = pd.DataFrame(columns=["mes", "despesas", "despesas_operacionais"])
    if df.empty:
        return vazia
    d = categorizar(df)
    saidas = d.loc[d["eh_saida"]]
    if saidas.empty:
        return vazia
    total = saidas.groupby("mes")["valor"].sum().reset_index()
    total.columns = ["mes", "despesas"]
    op = (saidas.loc[~saidas["categoria_n1"].isin(CATEGORIAS_NAO_OPERACIONAIS)]
          .groupby("mes")["valor"].sum().reset_index())
    op.columns = ["mes", "despesas_operacionais"]
    res = total.merge(op, on="mes", how="left").fillna(0)
    return res.sort_values("mes").reset_index(drop=True)


def custo_kg_mensal(df, kg_por_mes: dict) -> pd.DataFrame:
    """Série mensal ponderada de custo por kg com média acumulada corrida.

    Combina despesas mensais com a produção (kg) de cada mês e devolve:
      - mes, despesas, despesas_operacionais, kg
      - op_kg        : R$/kg operacional do mês (NaN quando kg = 0)
      - despesas_acum / kg_acum : acumulados (só operacional)
      - op_kg_acum   : média corrida (custo operacional acumulado ÷ kg acumulado).
                       Sempre tem valor a partir do 1º mês com produção, então a
                       linha nunca "quebra" em meses sem despesca.
    """
    vazia = pd.DataFrame(columns=[
        "mes", "despesas", "despesas_operacionais", "kg",
        "op_kg", "despesas_acum", "kg_acum", "op_kg_acum",
    ])
    if df.empty:
        return vazia
    base = custo_operacional_por_mes(df)
    base["kg"] = base["mes"].map(kg_por_mes).fillna(0).astype(float)
    base["op_kg"] = base.apply(
        lambda r: (r["despesas_operacionais"] / r["kg"]) if r["kg"] else float("nan"),
        axis=1)
    base["despesas_acum"] = base["despesas_operacionais"].cumsum()
    base["kg_acum"] = base["kg"].cumsum()
    base["op_kg_acum"] = base.apply(
        lambda r: (r["despesas_acum"] / r["kg_acum"]) if r["kg_acum"] else float("nan"),
        axis=1)
    return base.sort_values("mes").reset_index(drop=True)


def margem(df):
    """Margem (%) = resultado / receitas (pode ser negativo)."""
    r = resumo_geral(df)
    if r["receitas"] <= 0:
        return 0.0
    return r["resultado"] / r["receitas"] * 100


def custo_por_kg(custo_total, producao_kg):
    """Custo operacional por kg produzido."""
    if not producao_kg:
        return 0.0
    return custo_total / producao_kg


def lista_categorias(df, nivel="categoria_n1"):
    return sorted(df[nivel].dropna().unique().tolist())


def filtrar_periodo(df, data_inicio=None, data_fim=None):
    """Filtra o DataFrame por intervalo de datas (inclusive)."""
    if data_inicio is not None:
        df = df[df["data"] >= pd.Timestamp(data_inicio)]
    if data_fim is not None:
        df = df[df["data"] <= pd.Timestamp(data_fim)]
    return df


def filtrar_categorias(df, categorias_n1=None, categorias_n2=None):
    """Filtra por listas de categorias nível 1 e nível 2."""
    if categorias_n1:
        df = df[df["categoria_n1"].isin(categorias_n1)]
    if categorias_n2:
        df = df[df["categoria_n2"].isin(categorias_n2)]
    return df


def tabela_lancamentos(df, colunas=None):
    """Prepara o DataFrame para exibição na tabela (sem colunas auxiliares)."""
    if colunas is None:
        colunas = ["data", "tipo", "valor", "categoria_n1", "categoria_n2", "observacao"]
    presentes = [c for c in colunas if c in df.columns]
    out = df[presentes].copy()
    return out