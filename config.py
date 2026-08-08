"""Configuração do dashboard piscicultura.

Lê a configuração nesta ordem de precedência:
1. Segredos do Streamlit Cloud (st.secrets) — produção
2. Variáveis de ambiente
3. Arquivo .env do bot (desenvolvimento local)

Localiza a credencial da service account em bot/credenciais/ (mesma regra do bot).
"""
import os
from pathlib import Path

# Pasta raiz do projeto (pasta da Automação Planilha Piscicultura)
RAIZ = Path(__file__).resolve().parent.parent
PASTA_BOT = RAIZ / "bot"
PASTA_CREDENCIAIS = PASTA_BOT / "credenciais"
ARQUIVO_ENV = PASTA_BOT / ".env"

# Planilha local (cópia limpa) — usada como referência no diagnóstico e como
# fallback quando não há acesso ao Google Sheets (modo offline).
XLSX_REFERENCIA = RAIZ / "planilha" / "limpa" / "FLUXO DE CAIXA - Piscicultura Sempre Viva Julho 2026_LIMPA.xlsx"


def carregar_env(arquivo: Path) -> dict:
    """Parse simples do arquivo .env (sem dependências externas)."""
    if not arquivo.exists():
        return {}
    env = {}
    for linha in arquivo.read_text(encoding="utf-8", errors="replace").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        env[chave.strip()] = valor.strip().strip('"').strip("'")
    return env


def _secrets_streamlit():
    """Retorna dict com os segredos do Streamlit Cloud, se disponível.

    Normaliza as seções aninhadas (ex.: [service_account]) para dict real,
    pois em algumas versões do Streamlit o valor retornado é um objeto
    Mapping próprio, e não um dict nativo.
    """
    try:
        import streamlit as st

        if not hasattr(st, "secrets"):
            return {}
        base = dict(st.secrets)
        for chave, valor in list(base.items()):
            if isinstance(valor, dict):
                continue
            # Tenta converter Mapping/objeto de secrets em dict real.
            try:
                base[chave] = dict(valor)
            except Exception:
                base[chave] = str(valor)
        return base
    except Exception:
        return {}


def localizar_credencial() -> Path:
    """Localiza o JSON da service account em bot/credenciais/.

    Mesma regra do bot (src/google.js): o arquivo que contém "private_key".
    """
    if not PASTA_CREDENCIAIS.exists():
        raise FileNotFoundError(f"Pasta de credenciais não encontrada: {PASTA_CREDENCIAIS}")
    for caminho in sorted(PASTA_CREDENCIAIS.iterdir()):
        if caminho.suffix != ".json":
            continue
        try:
            conteudo = caminho.read_text(encoding="utf-8")
            if '"private_key"' in conteudo:
                return caminho
        except Exception:
            continue
    raise FileNotFoundError("Nenhum JSON de service account em bot/credenciais/")


def carregar_config():
    """Monta o dicionário de configuração consolidado."""
    secrets = _secrets_streamlit()
    env_bot = carregar_env(ARQUIVO_ENV)

    def obter(*nomes: str, padrao: str = "") -> str:
        for origem in (secrets, os.environ, env_bot):
            for nome in nomes:
                valor = origem.get(nome)
                if valor:
                    return str(valor)
        return padrao

    config = {
        "planilha_id": obter("PLANILHA_ID"),
        "aba_lancamentos": obter("ABA_LANCAMENTOS", padrao="Lançamentos"),
        "aba_revisão": obter("ABA_REVISAO", padrao="Revisão"),
        "pasta_credenciais": PASTA_CREDENCIAIS,
        "credencial": None,
        "credencial_dict": None,
        "xlsx_referencia": XLSX_REFERENCIA,
        "raiz": RAIZ,
    }

    # Credencial da service account é dict python: (Streamlit Cloud: segredo
    # `service_account = { ... }`; env local: JSON na pasta bot/credenciais/).
    cred_secrets = secrets.get("service_account")
    if not isinstance(cred_secrets, dict) and isinstance(cred_secrets, str):
        # Aceita a seção colada como JSON (linha única) no painel de secrets.
        import json as _json

        try:
            cred_secrets = _json.loads(cred_secrets)
        except Exception:
            cred_secrets = None
    if isinstance(cred_secrets, dict) and cred_secrets.get("private_key"):
        config["credencial"] = "secrets:service_account"
        config["credencial_dict"] = dict(cred_secrets)
    else:
        try:
            config["credencial"] = localizar_credencial()
        except FileNotFoundError:
            config["credencial"] = None
    return config