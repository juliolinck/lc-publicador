"""Despertador: garante que o Publicar rode na hora certa.

O agendamento do GitHub (cron) é "quando der": em repositórios com pouca
atividade ele atrasa horas ou simplesmente não roda. Este despertador fica
acordado no GitHub, olha a fila a cada minuto e, quando um post chega na hora,
dispara o workflow Publicar na mesma hora. Perto do limite de 6 horas de um
job do GitHub, ele dispara a si mesmo de novo e encerra, formando uma corrente
contínua. O cron de hora em hora do próprio despertador religa a corrente se
ela um dia cair.

O despertador não altera nenhum arquivo: quem publica e grava o resultado
continua sendo o Publicar.

Uso: python -m publicador.despertador [--minutos 340] [--uma-vez]
"""
import argparse, json, os, subprocess, sys, time
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "juliolinck/lc-publicador")
MAX_TENTATIVAS = int(os.environ.get("MAX_TENTATIVAS", "3"))
INTERVALO_SEG = int(os.environ.get("DESPERTADOR_INTERVALO_SEG", "60"))
REDISPARO_MIN = float(os.environ.get("DESPERTADOR_REDISPARO_MIN", "8"))  # espera mínima entre dois disparos


def log(msg):
    print(f"{datetime.now(timezone(timedelta(hours=-3))):%d/%m %H:%M:%S} {msg}", flush=True)


def gh(*args, entrada=None):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, input=entrada)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return r.stdout


def fila_atual():
    raw = gh("api", f"repos/{REPO}/contents/fila.json?ref=main",
             "-H", "Accept: application/vnd.github.raw+json")
    return json.loads(raw)


def quando(it):
    return datetime.fromisoformat(it["quando_utc"].replace("Z", "+00:00"))


def devidos(fila, agora):
    out = []
    for it in fila.get("itens", []):
        st = it.get("status")
        if st == "pendente" or (st == "erro" and it.get("tentativas", 0) < MAX_TENTATIVAS):
            if quando(it) <= agora:
                out.append(it)
    return out


def publicar_ativo():
    """True se já há um Publicar na fila ou rodando (evita disparos repetidos)."""
    raw = gh("api", f"repos/{REPO}/actions/workflows/publicar.yml/runs?per_page=5")
    for run in json.loads(raw).get("workflow_runs", []):
        if run.get("status") in ("queued", "in_progress", "waiting", "pending", "requested"):
            return True
    return False


def disparar(fluxo):
    gh("workflow", "run", fluxo, "--repo", REPO, "--ref", "main")


def rodar(minutos, uma_vez=False):
    inicio = time.monotonic()
    ultimo = None
    while True:
        agora = datetime.now(timezone.utc)
        try:
            lista = devidos(fila_atual(), agora)
            if lista:
                pronto = ultimo is None or time.monotonic() - ultimo >= REDISPARO_MIN * 60
                if pronto and not publicar_ativo():
                    disparar("publicar.yml")
                    ultimo = time.monotonic()
                    log("disparei o Publicar para: " + ", ".join(f"{i['id']} ({i['quando_local']})" for i in lista))
        except Exception as e:  # erro passageiro da API: tenta de novo no próximo minuto
            log(f"aviso: {e}")
        if uma_vez:
            return
        if time.monotonic() - inicio >= minutos * 60:
            break
        time.sleep(INTERVALO_SEG)
    try:
        disparar("despertador.yml")
        log("turno encerrado; próximo despertador disparado")
    except Exception as e:
        log(f"não consegui disparar o próximo despertador ({e}); o cron de hora em hora religa")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutos", type=float, default=340)
    ap.add_argument("--uma-vez", action="store_true")
    a = ap.parse_args()
    rodar(a.minutos, a.uma_vez)


if __name__ == "__main__":
    main()
