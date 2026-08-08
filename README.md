# Dashboard Fluxo de Caixa — Piscicultura Sempre Viva

Dashboard interativo da planilha de fluxo de caixa, feito com **Streamlit +
Pandas + Plotly**. Lê a aba `Lançamentos` direto do **Google Sheets** (fonte da
verdade, atualizada em tempo real pelo bot do WhatsApp) e recalcula os
indicadores em código — não depende das fórmulas da planilha.

## O que mostra

- **KPIs:** receitas, despesas, resultado, **% da ração no custo** e margem.
- **Evolução temporal:** receitas × despesas por mês + linha do saldo acumulado.
- **Composição de custos:** sunburst (categoria n1 → n2), pizza e barras com %.
- **Ração:** evolução mensal do percentual de ração sobre o custo.
- **Custo de produção (R$/kg):** cruzando despesas com a produção em kg da aba
  `Análises`/`Relatório 1`.
- **Tabela de lançamentos** filtrável, com botão de download em CSV.

Filtros na barra lateral: período (datas) e categorias nível 1. A página se
atualiza sozinha a cada **60 segundos** (refletindo lançamentos que chegam pelo
bot no Google Sheets).

## Como rodar local

```bash
# 1. use o venv da raiz do projeto (já tem as dependências instaladas)
cd "Automação Planilha Piscicultura/dashboard"

# 2. (primeira vez) garanta as dependências
"..\..\.venv\Scripts\python" -m pip install -r requirements.txt

# 3. rode
"..\..\.venv\Scripts\streamlit.exe" run app.py
```

O dashboard abre em `http://localhost:8501`. Ele lê a planilha do Google Sheets
usando a **service account** do bot (`bot/credenciais/piscicultura-sempre-viva-*.json`)
e o `PLANILHA_ID` do `bot/.env`. Para o modo offline (testar sem acesso ao
Google), o `diagnostico.py` e o `dados.py` usam a cópia limpa do xlsx em
`planilha/limpa/`.

## Diagnóstico

```bash
cd "Automação Planilha Piscicultura/dashboard"
"..\..\.venv\Scripts\python.exe" diagnostico.py            # diagnóstico completo
"..\..\.venv\Scripts\python.exe" diagnostico.py comparar   # Sheets x xlsx
```

Valida conexão, credenciais, saldos (E1/G1) e confronta a quantidade de
lançamentos entre o Google Sheets e o xlsx local.

## Publicação na nuvem (Streamlit Community Cloud)

O app está pronto para subir de graça: `app.py` na raiz do diretório publicada,
`requirements.txt` com as dependências. No painel do Streamlit Cloud configure
o segredo `senha_dashboard` (opcional) — veja `secrets.example.toml`.

Passos resumidos:

1. Crie um repositório **separado** contendo **apenas** a pasta `dashboard/`
   (não suba `bot/`, `.env` nem `credenciais/`).
2. No Streamlit Community Cloud, conecte o repositório → Main file `app.py`.
3. Em *Advanced settings ← Manage app → Secrets*, cole o conteúdo do
   `secrets.example.toml` preenchido (a `senha_dashboard` e, se necessário, o
   JSON da service account como `service_account = { ... }`).
   - Para o app na nuvem acessar a planilha, a service account já é editora da
     planilha; a credencial pode ser enviada via secrets em vez de depender do
     arquivo local do `bot/credenciais/`.
4. Pronto: quem tiver a URL e a senha acompanha o caixa em tempo real.

> O `config.py` dá prioridade aos segredos do Streamlit sobre o `.env` local,
> então a duplicação é opcional — sem segredos definidos, usa o `.env` do bot
> e as credenciais locais.