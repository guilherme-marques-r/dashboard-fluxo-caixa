"""Gráficos Plotly do dashboard (todas as visualizações interativas)."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta coerente com o bot (verde receita, vermelho despesa, azul saldo)
COR_RECEITA = "#2e7d32"
COR_DESPESA = "#c62828"
COR_SALDO = "#1565c0"
COR_RACAO = "#e65100"
COR_NEUTRO = "#6d4c41"

FONTE = "Segoe UI, Arial, sans-serif"


def _layout(base, titulo=None, altura=420):
    fig = go.Figure(base)
    fig.update_layout(
        template="plotly_white",
        title=titulo,
        height=altura,
        font={"family": FONTE},
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        hoverlabel={"namelength": -1},
    )
    return fig


def grafico_fluxo_mensal(fluxo: pd.DataFrame) -> go.Figure:
    """Barras de receitas/despesas + linha do saldo acumulado."""
    if fluxo.empty:
        return _layout([], "Receitas x Despesas por mês")
    base = [
        go.Bar(x=fluxo["mes"], y=fluxo["receitas"], name="Receitas",
               marker_color=COR_RECEITA,
               hovertemplate="%{x}<br>Receitas: R$ %{y:,.2f}<extra></extra>"),
        go.Bar(x=fluxo["mes"], y=fluxo["despesas"], name="Despesas",
               marker_color=COR_DESPESA,
               hovertemplate="%{x}<br>Despesas: R$ %{y:,.2f}<extra></extra>"),
    ]
    if "saldo" in fluxo.columns:
        base.append(go.Scatter(
            x=fluxo["mes"], y=fluxo["saldo"], name="Caixa acumulado",
            mode="lines+markers", line={"color": COR_SALDO, "width": 2.5},
            hovertemplate="%{x}<br>Caixa: R$ %{y:,.2f}<extra></extra>",
        ))
    fig = _layout(base, "Receitas x Despesas por mês")
    fig.update_layout(barmode="group", xaxis_tickangle=-45,
                      legend={"orientation": "h", "y": 1.12})
    return fig


def grafico_composicao(composicao: pd.DataFrame) -> go.Figure:
    """Barras horizontais de composição de despesas com %."""
    vazia = _layout([], "Composição das despesas por categoria")
    if composicao.empty:
        return vazia
    comp = composicao.sort_values("valor")
    base = [go.Bar(
        x=comp["valor"], y=comp["categoria"], orientation="h",
        marker_color=COR_NEUTRO,
        customdata=comp["pct"],
        text=[f"{p:.1f}%" for p in comp["pct"]],
        textposition="outside",
        hovertemplate="%{y}<br>R$ %{x:,.2f} (%{customdata:.1f}%)<extra></extra>",
    )]
    return _layout(base, "Composição das despesas por categoria", altura=380)


def grafico_custo_capex(compost_capex: pd.DataFrame) -> go.Figure:
    """Dona separando custo operacional × capex (Investimento + Fábrica Ração)."""
    vazia = _layout([], "Operacional × Investimento/Fábrica Ração")
    if compost_capex.empty:
        return vazia
    cores_dic = {"Custo operacional": COR_RACAO,
                 "Investimento + Fábrica Ração": COR_NEUTRO}
    fig = px.pie(compost_capex, names="categoria", values="valor",
                 hole=0.4)
    fig.update_traces(textinfo="percent+label",
                      marker=dict(colors=[cores_dic.get(c, COR_NEUTRO)
                                          for c in compost_capex["categoria"]]),
                      hovertemplate="%{label}<br>R$ %{value:,.2f} (%{percent})<extra></extra>")
    fig.update_layout(title="Fábrica Ração/Investimento vs operação",
                       template="plotly_white", font={"family": FONTE},
                       legend=dict(x=0, y=0.5))
    return fig


def grafico_racao_mensal(racao: pd.DataFrame) -> go.Figure:
    """Evolução do % da ração sobre o custo (linha + área)."""
    if racao.empty:
        return _layout([], "Percentual do custo gasto em ração por mês")
    comp = go.Scatter(
        x=racao["mes"], y=racao["pct_racao"],
        mode="lines+markers", line={"color": COR_RACAO, "width": 3},
        fill="tozeroy", fillcolor="rgba(230,81,0,0.12)",
        customdata=racao[["racao", "custo_total"]],
        hovertemplate="%{x}<br>R$ %{y:,.1f}% do custo era ração<br>"
                      "Ração R$ %{customdata[0]:,.2f} de R$ %{customdata[1]:,.2f}<extra></extra>",
    )
    return _layout([comp], "Percentual do custo gasto em ração por mês")


def grafico_sunburst(df: pd.DataFrame) -> go.Figure:
    """Sunburst n1 → n2 das despesas."""
    vazio = _layout([], "Composição hierárquica")
    if df.empty:
        return vazio
    d = df.copy()
    saidas = d[d["tipo"].str.lower().str.startswith("saida")]
    if saidas.empty:
        return vazio
    agrupado = (saidas.groupby(["categoria_n1", "categoria_n2"], dropna=False)
                .agg(total=("valor", "sum"))
                .reset_index())
    labels, parents, values = [], [], []
    for n1, total in agrupado.groupby("categoria_n1")["total"].sum().items():
        rot = str(n1)
        labels.append(rot if rot not in labels else f"{rot} (n1)")
        parents.append("")
        values.append(total)
        for _, r in agrupado[agrupado["categoria_n1"] == n1].iterrows():
            labels.append(f"{rot} / {r['categoria_n2']}")
            parents.append(rot if rot in labels else f"{rot} (n1)")
            values.append(r["total"])
    base = [go.Sunburst(
        labels=labels, parents=parents, values=values,
        hovertemplate="%{label}<br>R$ %{value:,.2f}<extra></extra>",
    )]
    return _layout(base, "Custo por categoria (nível 1 → nível 2)")


def grafico_custo_kg(dados_kg: pd.DataFrame) -> go.Figure:
    """Custo de produção por kg — híbrido: barras de custo + linhas de R$/kg.

    - Eixo Y esquerdo (R$/kg): média acumulada corrida (nunca quebra) e R$/kg
      mensal do operacional.
    - Eixo Y direito (R$): despesas do mês (barras), que dão contexto a meses
      sem despesa (kg = 0) como junho/2026.
    - Meses com custo mas sem despesca ganham um selo discreto "sem despesca".
    """
    vazio = _layout([], "Custo de produção (R$/kg)")
    if dados_kg.empty:
        return vazio

    d = dados_kg.copy()
    linha_mensal = d.loc[d["kg"] > 0]
    sem_despesca = d.loc[(d["kg"] == 0) & (d["despesas"] > 0)]

    base = [
        # Barras: custo do mês (eixo direito). Transparente p/ não esconder linhas.
        go.Bar(
            x=d["mes"], y=d["despesas"], name="Custo do mês",
            marker_color="rgba(38,125,50,0.16)", marker_line={"width": 0},
            yaxis="y2", opacity=1.0,
            hovertemplate="%{x}<br>Custo do mês: R$ %{y:,.2f}<extra></extra>",
        ),
    ]

    # Média acumulada corrida (operacional) — contínua, passa por junho/agosto.
    media = d.loc[d["op_kg_acum"].notna(), ["mes", "op_kg_acum"]]
    if len(media):
        base.append(go.Scatter(
            x=media["mes"], y=media["op_kg_acum"],
            mode="lines+markers", name="Média corrida (R$/kg)",
            line={"color": COR_SALDO, "width": 3},
            marker={"size": 6},
            hovertemplate="%{x}<br>Média corrida: R$ %{y:,.2f}/kg<extra></extra>",
        ))

    # R$/kg mensal (somente meses com despesca).
    if not linha_mensal.empty:
        base.append(go.Scatter(
            x=linha_mensal["mes"], y=linha_mensal["op_kg"],
            mode="lines+markers", name="R$/kg do mês (operacional)",
            line={"color": COR_RACAO, "width": 2},
            marker={"size": 7},
            connectgaps=False,
            hovertemplate="%{x}<br>R$/kg do mês: R$ %{y:,.2f}<extra></extra>",
        ))

    # Selo nos meses com custo mas sem despesca (ex.: junho/2026).
    if len(sem_despesca):
        base.append(go.Scatter(
            x=sem_despesca["mes"],
            y=[0.0] * len(sem_despesca),
            mode="markers", name="Sem despesca",
            marker={"color": "#9e9e9e", "size": 13, "symbol": "triangle-down"},
            customdata=sem_despesca[["mes", "despesas"]].to_numpy(),
            hovertemplate="%{customdata[0]}: sem despesca<br>"
                          "Custo: R$ %{customdata[1]:,.2f}<extra></extra>",
        ))

    fig = _layout(base, "Custo de produção (R$/kg) — média corrida × mensal")
    fig.update_layout(
        barmode="overlay",
        xaxis_tickangle=-45,
        legend={"orientation": "h", "y": 1.12},
        # Eixo direito para as barras de custo.
        yaxis2=dict(title="Custo do mês (R$)", overlaying="y", side="right",
                    showgrid=False, automargin=True),
    )
    return fig


def grafico_pizza(comp, titulo="Distribuição de despesas"):
    if comp.empty:
        return _layout([], titulo)
    fig = px.pie(comp, names="categoria", values="valor",
                 title=titulo, hole=0.4)
    fig.update_traces(textinfo="percent+label",
                      hovertemplate="%{label}<br>R$ %{value:,.2f} (%{percent})<extra></extra>")
    fig.update_layout(template="plotly_white", font={"family": FONTE},
                      legend_title="Categoria", legend=dict(x=0, y=0.5))
    return fig