"""Dashboard interativo do fluxo de caixa da Piscicultura Sempre Viva.

Streamlit + Pandas + Plotly, lendo do Google Sheets (fonte da verdade, sempre
atualizada pelo bot do WhatsApp) com fallback para o xlsx local. A página é
recarregada automaticamente a cada 60 s, refletindo os lançamentos que o bot
grava na planilha em tempo real.

Uso local:  streamlit run app.py
"""
import pandas as pd
import streamlit as st

import dados
import metricas
import visual as vis
from config import carregar_config

CONFIG = carregar_config()

INTERVALO_REFRESH = 60  # segundos

st.set_page_config(
    page_title="Fluxo de Caixa - Piscicultura Sempre Viva",
    page_icon=":fish:",
    layout="wide",
    initial_sidebar_state="expanded",
)

MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


# ------------------------------------------------------------------- helpers
def _moeda(valor):
    """Formata float como moeda brasileira (R$ 1.234,56) de forma robusta."""
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return "R$ 0,00"
    negativo = valor < 0
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {'-' if negativo else ''}{texto}"


def _pct(valor):
    try:
        return f"{float(valor):,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "0,0%"


@st.cache_data(ttl=INTERVALO_REFRESH, show_spinner=False)
def carregar_lancamentos_cache():
    return dados.ler_lancamentos("sheets")


@st.cache_data(ttl=300, show_spinner=False)
def carregar_producao_cache():
    return dados.ler_producao_mensal()


@st.cache_data(ttl=INTERVALO_REFRESH, show_spinner=False)
def carregar_saldos_cache():
    return dados.ler_saldos("sheets")


# --------------------------------------------------------------------- acesso
def verificar_acesso():
    """Senha simples via segredo do Streamlit (produção). Local, segue sem senha."""
    senha_esperada = ""
    try:
        senha_esperada = st.secrets.get("senha_dashboard", "")
    except Exception:
        pass
    if not senha_esperada:
        return True
    if st.session_state.get("dashboard_autenticado"):
        return True
    senha = st.sidebar.text_input("Senha do dashboard", type="password")
    if senha and senha == senha_esperada:
        st.session_state["dashboard_autenticado"] = True
        return True
    if senha:
        st.sidebar.error("Senha incorreta.")
    st.sidebar.info("Digite a senha para visualizar o dashboard.")
    return False


def _nome_mes(data):
    return f"{MESES_PT[data.month - 1]} de {data.year}"


# ----------------------------------------------------------------------- main
def main():
    if not verificar_acesso():
        return

    st.title(":fish: Fluxo de Caixa — Piscicultura Sempre Viva")
    st.caption(f"Fonte: aba *Lançamentos* do Google Sheets · atualização a cada "
               f"{INTERVALO_REFRESH}s (sem recarregar a página).")

    if CONFIG["credencial"] is None:
        st.error("Credencial da service account não encontrada. Verifique `bot/credenciais/`.")
        return

    painel_dashboard()


@st.fragment(run_every=INTERVALO_REFRESH)
def painel_dashboard():
    # `st.fragment(run_every=...)` reexecuta SÓ este bloco. O resto da página
    # não precisa recarregar, então não aparece o desfoque/opacidade global.
    try:
        df = carregar_lancamentos_cache()
        producao = carregar_producao_cache()
        saldos = carregar_saldos_cache()
    except Exception as e:
        st.error(f"Não foi possível ler a planilha: {e}")
        st.info("Rode `python diagnostico.py` para investigar.")
        return

    if df.empty:
        st.warning("Nenhum lançamento encontrado na planilha.")
        return

    # Só avisa (de forma discreta) quando houver lançamentos novos.
    chave = f"dados_{len(df)}_{df['data'].max().isoformat() if not df.empty else ''}"
    if st.session_state.get("ultimo_estado_dados") not in (None, "") \
            and st.session_state["ultimo_estado_dados"] != chave:
        st.toast(":bell: Dados atualizados — novos lançamentos recebidos.", icon="📊")
    st.session_state["ultimo_estado_dados"] = chave

    # ------------------------------------------------------------- filtros
    with st.sidebar:
        st.header("Filtros")
        data_min = df["data"].dt.date.min()
        data_max = df["data"].dt.date.max()
        periodo = st.date_input(
            "Período",
            value=(data_min, data_max),
            min_value=data_min,
            max_value=data_max,
            format="DD/MM/YYYY",
        )
        ini, fnn = (periodo if isinstance(periodo, tuple) and len(periodo) == 2
                    else (data_min, data_max))

        cats = metricas.lista_categorias(df)
        cats_sel = st.multiselect("Categorias (nível 1)", cats, default=cats)

        st.divider()
        st.caption("Diagnóstico a qualquer momento:\n`python diagnostico.py` na pasta `dashboard/`.")

    df_f = metricas.filtrar_periodo(df, pd.Timestamp(ini), pd.Timestamp(fnn))
    if cats_sel:
        df_f = metricas.filtrar_categorias(df_f, cats_sel)

    geral = metricas.resumo_geral(df_f)
    saldo_inicial = float(saldos.get("saldo_inicial", 0.0))
    fluxo = metricas.fluxo_mensal(df_f, saldo_inicial=saldo_inicial)
    comp_n1 = metricas.composicao_despesas(df_f)
    comp_n2 = metricas.composicao_despesas(df_f, nivel="categoria_n2")
    comp_capex = metricas.composicao_capex(df_f)
    pct_racao = metricas.racao_sobre_custo(df_f)
    margem = metricas.margem(df_f)
    racao_mes = metricas.racao_por_mes(df_f)

    # --------------------------------------------------------------- KPI/caixa
    st.subheader(_nome_mes(pd.Timestamp(fnn)))
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Receitas", _moeda(geral["receitas"]))
    c2.metric("Despesas", _moeda(geral["despesas"]))
    c3.metric("Resultado", _moeda(geral["resultado"]))
    c4.metric("Caixa", _moeda(fluxo.iloc[-1]["saldo"] if not fluxo.empty else saldo_inicial))
    c5.metric("Ração no custo", _pct(pct_racao))
    c6.metric("Margem", _pct(margem))
    st.caption(f"Resultado = receitas − despesas do período. Caixa = resultado + "
               f"saldo inicial (R$ {_moeda(saldo_inicial)}). Não há lançamento de "
               f"entrada do saldo inicial; ele vive só na célula E1 da planilha.")

    st.plotly_chart(vis.grafico_fluxo_mensal(fluxo), use_container_width=True, key="fluxo")

    # --------------------------------------------------------------- gráficos
    col_a, col_b = st.columns([1.3, 1])
    with col_a:
        st.plotly_chart(vis.grafico_pizza(comp_n1, "Distribuição das despesas (n1)"),
                        use_container_width=True, key="pizza_n1")
    with col_b:
        st.plotly_chart(vis.grafico_custo_capex(comp_capex), use_container_width=True, key="capex")

    st.subheader("Composição dos custos")
    st.plotly_chart(vis.grafico_composicao(comp_n2), use_container_width=True, key="comp_n2")

    st.subheader("Ração e custo de produção")
    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(vis.grafico_racao_mensal(racao_mes), use_container_width=True, key="racao")
    with col4:
        st.plotly_chart(vis.grafico_custo_kg(metricas.custo_kg_mensal(df_f, producao)),
                        use_container_width=True, key="custokg")

    # ---------------------------------------------------------- lançamentos
    st.subheader("Tabela de lançamentos")
    aba_lanc, aba_resumo = st.tabs(["Lançamentos do período", "Resumo mensal"])
    with aba_lanc:
        tab = metricas.tabela_lancamentos(df_f)
        tab["data"] = tab["data"].dt.strftime("%d/%m/%Y")
        tab["valor"] = tab["valor"].round(2)
        st.dataframe(tab, use_container_width=True, hide_index=True, key="tab_lanc")
        st.download_button(
            "Baixar CSV",
            data=tab.to_csv(index=False).encode("utf-8-sig"),
            file_name="lancamentos_fluxo_caixa.csv",
            mime="text/csv",
        )
    with aba_resumo:
        resumo = fluxo.copy()
        resumo.columns = ["Mês", "Receitas", "Despesas", "Resultado", "Caixa acumulado"]
        st.dataframe(resumo.round(2), use_container_width=True, hide_index=True, key="tab_resumo")


main()