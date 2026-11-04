"""Publica o que está na hora. Roda a cada 10 minutos no GitHub (ou à mão).

Uso: python -m publicador.executar [--seco] [--agora AAAA-MM-DDTHH:MM]
  --seco   mostra o que seria publicado, sem chamar a Meta
  --agora  simula outro horário (para testes)
"""
import argparse, json, os
from datetime import datetime, timedelta, timezone
from . import config, fila as F, meta

ESTADO = os.path.join(config.RAIZ, "estado.json")

def gravar_estado(ok, erro=""):
    """Guarda se o acesso à Meta está funcionando, para o app avisar."""
    antes = json.load(open(ESTADO, encoding="utf-8")) if os.path.exists(ESTADO) else {}
    novo = {"acesso_ok": ok, "erro": erro, "desde": antes.get("desde") if antes.get("acesso_ok") == ok else F.agora_utc().strftime("%Y-%m-%dT%H:%M:%SZ")}
    if novo != antes:
        with open(ESTADO, "w", encoding="utf-8") as f: json.dump(novo, f, ensure_ascii=False, indent=1)

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
                gravar_estado(True)
            except meta.ErroAcesso as e:
                # O problema é o acesso, não o post: não gasta tentativa e para a rodada.
                it["tentativas"] -= 1
                if not it["resultado"]: it["status"] = "pendente"
                F.salvar(fila)
                F.registrar(f"ACESSO RECUSADO pela Meta ao publicar {it['id']} — {e}")
                gravar_estado(False, str(e))
                print("Acesso à Meta recusado; nada mais será tentado nesta rodada.")
                return feitos
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
