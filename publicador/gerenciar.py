"""Ajustes rápidos na fila.

Uso:
  python -m publicador.gerenciar listar [--pendentes]
  python -m publicador.gerenciar pausar ID          (não publica até retomar)
  python -m publicador.gerenciar retomar ID
  python -m publicador.gerenciar mover ID "DD/MM/AAAA HH:MM"   (novo horário de Brasília)
  python -m publicador.gerenciar repetir ID         (zera as tentativas de um item com erro ou perdido)
  python -m publicador.gerenciar remover ID
  python -m publicador.gerenciar limpar [DIAS]      (apaga mídias de posts publicados há mais de DIAS dias; padrão 7)
"""
import sys, os, shutil
from datetime import datetime, timedelta, timezone
from . import config, fila as F

def _achar(fila, iid):
    itens = [i for i in fila["itens"] if i["id"] == iid]
    if not itens: sys.exit(f"ID {iid} não está na fila")
    return itens

def main(argv=None):
    a = argv or sys.argv[1:]
    if not a: print(__doc__); return
    cmd, fila = a[0], F.carregar()
    if cmd == "listar":
        for i in fila["itens"]:
            if "--pendentes" in a and i["status"] != "pendente": continue
            print(f"{i['quando_local']}  {i['id']:<4} {i['tipo']:<9} {i['status']:<9} {i['titulo'][:60]}  {i.get('erro','')[:80]}")
        return
    if cmd == "limpar":
        dias = int(a[1]) if len(a) > 1 else 7
        lim = F.agora_utc() - timedelta(days=dias); n = 0
        for i in fila["itens"]:
            if i["status"] == "publicado" and F.quando(i) < lim and i["arquivos"]:
                shutil.rmtree(os.path.join(config.MIDIA, i["id"]), ignore_errors=True); i["arquivos_removidos"] = True; n += 1
        F.salvar(fila); print(f"mídias removidas de {n} posts publicados"); return
    if len(a) < 2: sys.exit(__doc__)
    iid = a[1]
    if cmd == "remover":
        fila["itens"] = [i for i in fila["itens"] if i["id"] != iid]
    else:
        for i in _achar(fila, iid):
            if cmd == "pausar": i["status"] = "pausado"
            elif cmd == "retomar": i["status"] = "pendente"
            elif cmd == "repetir": i["status"] = "pendente"; i["tentativas"] = 0; i["erro"] = ""
            elif cmd == "mover":
                local = datetime.strptime(a[2], "%d/%m/%Y %H:%M").replace(tzinfo=config.FUSO)
                i["quando_utc"] = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                i["quando_local"] = local.strftime("%d/%m/%Y %H:%M")
                if i["status"] in ("perdido", "erro"): i["status"] = "pendente"; i["tentativas"] = 0
            else: sys.exit(__doc__)
    fila["itens"].sort(key=lambda x: x["quando_utc"])
    F.salvar(fila); F.registrar(f"AJUSTE {cmd} {iid}")

if __name__ == "__main__":
    main()
