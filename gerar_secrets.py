"""Gera o bloco de segredos para colar no painel do Streamlit Community Cloud.

Lê a credencial local da service account (bot/credenciais/*.json) e o
PLANILHA_ID do bot/.env, e imprime o conteúdo TOML de `secrets.toml`.
Cuidado: imprime a chave privada no terminal — só rode na sua máquina.

Uso:  python gerar_secrets.py  [minha-senha]
"""
import json
import sys
from pathlib import Path

from config import carregar_config

CONFIG = carregar_config()


def _encode(valor):
    # TOML: strings multi-linha (private_key tem \n) entre aspas triplas.
    texto = str(valor)
    if "\n" in texto:
        return '"""\n' + texto + '\n"""'
    if any(c in texto for c in '"\\'):
        return json.dumps(texto)
    return f'"{texto}"'


def main():
    senha = sys.argv[1] if len(sys.argv) > 1 else "COLOQUE_UMA_SENHA"
    if not CONFIG.get("planilha_id"):
        print("PLANILHA_ID não encontrado no .env do bot.", file=sys.stderr)
        return 1
    cred = CONFIG.get("credencial_dict")
    if not cred:
        caminho = CONFIG["credencial"]
        if not hasattr(caminho, "read_text"):
            print(f"Credencial não encontrada: {CONFIG['credencial']}", file=sys.stderr)
            return 1
        cred = json.loads(Path(caminho).read_text(encoding="utf-8"))

    print("senha_dashboard = " + _encode(senha))
    print("PLANILHA_ID = " + _encode(CONFIG["planilha_id"]))
    print()
    print("[service_account]")
    for k, v in cred.items():
        print(f"{k} = {_encode(v)}")
    print()
    print("# Copie a partir de 'senha_dashboard' até o fim deste bloco para o painel Secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())