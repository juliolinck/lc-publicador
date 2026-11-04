"""Coleta diária: seguidores da conta e números de cada post publicado nos últimos 30 dias.

Uso: python -m publicador.metricas
"""
import json, os
from datetime import timedelta
from . import config, fila as F, meta

def coletar():
    dados = json.load(open(config.METRICAS, encoding="utf-8")) if os.path.exists(config.METRICAS) else {"seguidores": [], "posts": {}}
    hoje = F.agora_utc().astimezone(config.FUSO).strftime("%Y-%m-%d")
    try:
        c = meta.conta()
        dados["conta"] = {k: c.get(k) for k in ("username", "followers_count", "follows_count", "media_count")}
        dados["seguidores"] = [s for s in dados["seguidores"] if s["dia"] != hoje] + [{"dia": hoje, "total": c.get("followers_count")}]
        F.registrar(f"MÉTRICAS seguidores hoje: {c.get('followers_count')}")
        from .executar import gravar_estado; gravar_estado(True)
    except meta.ErroAcesso as e:
        F.registrar(f"MÉTRICAS falhou ao ler a conta: {e}")
        from .executar import gravar_estado; gravar_estado(False, str(e))
    except Exception as e:
        F.registrar(f"MÉTRICAS falhou ao ler a conta: {e}")
    limite = F.agora_utc() - timedelta(days=30)
    for it in F.carregar()["itens"]:
        r = it.get("resultado", {}).get("instagram", {})
        if not r.get("id") or F.quando(it) < limite: continue
        m = meta.metricas_post(r["id"], it["tipo"] == "reel")
        if m:
            dados["posts"][it["id"]] = {"dia": hoje, **m}
    with open(config.METRICAS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    coletar()
