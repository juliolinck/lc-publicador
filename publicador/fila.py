"""Leitura e gravação da fila de publicação (fila.json)."""
import json, os
from datetime import datetime, timezone
from . import config

STATUS = ("pendente", "publicado", "erro", "perdido", "pausado")

def carregar():
    if not os.path.exists(config.FILA):
        return {"itens": []}
    with open(config.FILA, encoding="utf-8") as f:
        return json.load(f)

def salvar(fila):
    tmp = config.FILA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(fila, f, ensure_ascii=False, indent=1)
    os.replace(tmp, config.FILA)

def agora_utc():
    return datetime.now(timezone.utc)

def quando(item):
    return datetime.fromisoformat(item["quando_utc"].replace("Z", "+00:00"))

def registrar(msg):
    linha = f"{agora_utc().astimezone(config.FUSO):%d/%m/%Y %H:%M} {msg}"
    print(linha, flush=True)
    with open(config.REGISTRO, "a", encoding="utf-8") as f:
        f.write(linha + "\n")
