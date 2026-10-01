"""Contas de clientes guardadas em um arquivo JSON simples (data/contas.json).

Formato:
{
  "contas": [
    {"id": "...", "nome": "...", "email": "...", "senha_hash": "pbkdf2_sha256$...", "criado_em": "..."}
  ]
}

A senha NUNCA é guardada em texto: só o hash (o mesmo formato seguro do Django).
"""
import json
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password

_lock = threading.RLock()


class ContasJsonErro(Exception):
    """Arquivo ilegível/corrompido ou impossível de gravar."""


class ContaJaExiste(Exception):
    pass


def normalizar(email):
    return (email or "").strip().lower()


def _ler():
    caminho = settings.CONTAS_JSON_PATH
    if not caminho.exists():
        return {"contas": []}
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError) as erro:
        # Não sobrescrevemos um arquivo que não conseguimos ler: as contas não podem ser perdidas.
        raise ContasJsonErro(f"Não foi possível ler {caminho}: {erro}") from erro
    if not isinstance(dados, dict) or not isinstance(dados.get("contas"), list):
        raise ContasJsonErro(f"Formato inesperado em {caminho}")
    return dados


def _gravar(dados):
    """Grava de forma atômica: escreve num arquivo temporário e troca pelo definitivo."""
    caminho = settings.CONTAS_JSON_PATH
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(dir=caminho.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        for tentativa in range(5):  # no Windows/OneDrive o arquivo pode estar momentaneamente travado
            try:
                os.replace(temporario, caminho)
                return
            except PermissionError:
                if tentativa == 4:
                    raise
                time.sleep(0.15)
    except OSError as erro:
        raise ContasJsonErro(f"Não foi possível gravar {caminho}: {erro}") from erro
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)


def buscar(email):
    email = normalizar(email)
    with _lock:
        for conta in _ler()["contas"]:
            if conta.get("email") == email:
                return conta
    return None


def criar(nome, email, senha=None, senha_hash=None):
    """Cria a conta. Passe `senha` (texto) ou `senha_hash` (já pronto, para importar)."""
    email = normalizar(email)
    with _lock:
        dados = _ler()
        if any(c.get("email") == email for c in dados["contas"]):
            raise ContaJaExiste(email)
        conta = {
            "id": str(uuid.uuid4()),
            "nome": nome,
            "email": email,
            "senha_hash": senha_hash or make_password(senha),
            "criado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        dados["contas"].append(conta)
        _gravar(dados)
    return conta


def autenticar(email, senha):
    """Devolve a conta se e-mail e senha conferem; senão None."""
    conta = buscar(email)
    if conta is None:
        make_password(senha)  # gasta o mesmo tempo, para não revelar se o e-mail existe
        return None
    return conta if check_password(senha, conta.get("senha_hash", "")) else None
