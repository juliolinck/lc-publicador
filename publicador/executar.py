"""Publica o que está na hora. Roda a cada 10 minutos no GitHub (ou à mão).

Uso: python -m publicador.executar [--seco] [--agora AAAA-MM-DDTHH:MM]
  --seco   mostra o que seria publicado, sem chamar a Meta
  --agora  simula outro horário (para testes)
"""
import argparse
from datetime import datetime, timedelta, timezone
from . import config, fila as F, meta

def redes():
    r = ["instagram"]
    if config.PUBLICAR_FACEBOOK and config.FB_PAGINA:
        r.append("facebook")
    return r

def devidos(fila, agora):
    for it in fila["itens"]:
        if it["status"] in ("publicado", "perdido", "pausado"): continue
        if it["status"] == "erro" and it["tentativas"] >= config.MAX_TENTATIVAS: continue
        if F.quando(it) <= agora:
            yield it

def executar(seco=False, agora=None):
    agora = agora or F.agora_utc()
    fila = F.carregar()
    lista = list(devidos(fila, agora))
    if not lista:
        print("Nada para publicar agora."); return 0
    feitos = 0
    for it in lista:
        atraso = agora - F.quando(it)
        if atraso > timedelta(hours=config.ATRASO_MAXIMO_HORAS) and it["tentativas"] == 0:
            it["status"] = "perdido"; it["erro"] = f"passou {atraso} do horário sem ser publicado"
            F.registrar(f"PERDIDO {it['id']} {it['quando_local']} — {it['titulo']}")
            F.salvar(fila); continue
        if seco:
            print(f"[seco] publicaria {it['id']} ({it['tipo']}) {it['quando_local']} — {it['titulo']}")
            continue
        it["tentativas"] += 1
        it.setdefault("resultado", {})
        erros = []
        for rede in redes():
            if it["resultado"].get(rede, {}).get("id"):
                continue  # já saiu nesta rede numa tentativa anterior
            try:
                res = meta.instagram(it) if rede == "instagram" else meta.facebook(it)
                res["em"] = F.agora_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
                it["resultado"][rede] = res
                F.registrar(f"OK {rede} {it['id']} — {it['titulo']} {res.get('link', '')}")
            except Exception as e:
                erros.append(f"{rede}: {e}")
                F.registrar(f"ERRO {rede} {it['id']} (tentativa {it['tentativas']}) — {e}")
        if erros:
            it["status"] = "erro"; it["erro"] = " | ".join(erros)
        else:
            it["status"] = "publicado"; it["erro"] = ""; feitos += 1
        F.salvar(fila)  # grava a cada item: se cair no meio, nada é publicado duas vezes
    print(f"{feitos} publicado(s) nesta rodada.")
    return feitos

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seco", action="store_true")
    ap.add_argument("--agora")
    a = ap.parse_args()
    agora = datetime.fromisoformat(a.agora).replace(tzinfo=config.FUSO).astimezone(timezone.utc) if a.agora else None
    executar(a.seco, agora)

if __name__ == "__main__":
    main()
