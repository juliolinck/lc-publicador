"""Ajustes rápidos na fila.

Uso:
  python -m publicador.gerenciar listar [--pendentes]
  python -m publicador.gerenciar pausar ID          (não publica até retomar)
  python -m publicador.gerenciar retomar ID
  python -m publicador.gerenciar mover ID "DD/MM/AAAA HH:MM"   (novo horário de Brasília)
  python -m publicador.gerenciar agora ID           (publica na próxima rodada)
  python -m publicador.gerenciar legenda ID "texto" (troca a legenda de um post ainda não publicado)
  python -m publicador.gerenciar titulo ID "texto"  (troca o título interno)
  python -m publicador.gerenciar repetir ID         (zera as tentativas de um item com erro ou perdido)
  python -m publicador.gerenciar remover ID
  python -m publicador.gerenciar limpar [DIAS]      (apaga mídias de posts publicados há mais de DIAS dias; padrão 7)
  python -m publicador.gerenciar lote               (aplica a lista JSON da variável COMANDOS; usado pelo app)
"""
import sys, os, json, shutil
from datetime import datetime, timedelta, timezone
from . import config, fila as F

COMANDOS = ("pausar", "retomar", "mover", "agora", "legenda", "titulo", "repetir", "remover", "novo")
SO_ANTES_DE_PUBLICAR = ("pausar", "mover", "agora", "legenda", "titulo")
TIPOS = ("imagem", "carrossel", "reel", "story")
VIDEO = (".mp4", ".mov", ".m4v")

def _definir_horario(i, local):
    i["quando_utc"] = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    i["quando_local"] = local.strftime("%d/%m/%Y %H:%M")

def _novo(fila, iid, valor):
    """Cria um post a partir do app. As mídias já foram gravadas em midia/<ID>/ pelo próprio app."""
    d = json.loads(valor or "{}")
    if not iid or any(i["id"] == iid for i in fila["itens"]):
        raise ValueError(f"código {iid} inválido ou já usado")
    tipo = d.get("tipo")
    if tipo not in TIPOS: raise ValueError(f"tipo inválido: {tipo}")
    arquivos = [a for a in d.get("arquivos", []) if a.startswith(f"midia/{iid}/")]
    if not arquivos: raise ValueError("nenhuma mídia")
    faltando = [a for a in arquivos if not os.path.exists(os.path.join(config.RAIZ, a))]
    if faltando: raise ValueError(f"mídia não encontrada: {', '.join(faltando)}")
    videos = [a for a in arquivos if a.lower().endswith(VIDEO)]
    if tipo == "imagem" and (len(arquivos) != 1 or videos): raise ValueError("post precisa de exatamente 1 imagem")
    if tipo == "reel" and (len(arquivos) != 1 or not videos): raise ValueError("reel precisa de exatamente 1 vídeo")
    if tipo == "story" and len(arquivos) != 1: raise ValueError("story precisa de exatamente 1 arquivo")
    if tipo == "carrossel" and not (2 <= len(arquivos) <= 10): raise ValueError("carrossel precisa de 2 a 10 arquivos")
    legenda = (d.get("legenda") or "").strip()
    if len(legenda) > 2200: raise ValueError("legenda passa de 2.200 caracteres")
    capa = d.get("capa") or ""
    if capa and not (capa.startswith(f"midia/{iid}/") and os.path.exists(os.path.join(config.RAIZ, capa))): capa = ""
    local = datetime.strptime(d.get("quando", "").strip(), "%d/%m/%Y %H:%M").replace(tzinfo=config.FUSO)
    item = dict(id=iid, titulo=(d.get("titulo") or "").strip() or "Post sem título", tipo=tipo,
                arquivos=arquivos, capa=capa, legenda=legenda, validar_juridico=False,
                status="pendente", tentativas=0, resultado={}, erro="", origem="app")
    _definir_horario(item, local)
    fila["itens"].append(item)
    return f"novo {iid} ({tipo}) para {item['quando_local']} — {item['titulo']}"

def aplicar(fila, cmd, iid, valor=""):
    """Aplica um comando a um item. Devolve uma frase para o registro (ou levanta ValueError)."""
    if cmd not in COMANDOS:
        raise ValueError(f"comando desconhecido: {cmd}")
    if cmd == "novo":
        return _novo(fila, iid, valor)
    if cmd == "remover":
        antes = len(fila["itens"])
        fila["itens"] = [i for i in fila["itens"] if not (i["id"] == iid and i["status"] != "publicado")]
        if len(fila["itens"]) == antes:
            raise ValueError(f"{iid} não está na fila ou já foi publicado")
        return f"removido {iid}"
    itens = [i for i in fila["itens"] if i["id"] == iid]
    if not itens:
        raise ValueError(f"{iid} não está na fila")
    for i in itens:
        if cmd in SO_ANTES_DE_PUBLICAR and i["status"] == "publicado":
            raise ValueError(f"{iid} já foi publicado")
        if cmd == "pausar":
            i["status"] = "pausado"
        elif cmd == "retomar":
            if i["status"] == "pausado": i["status"] = "pendente"
        elif cmd == "repetir":
            i["status"] = "pendente"; i["tentativas"] = 0; i["erro"] = ""
        elif cmd == "mover":
            local = datetime.strptime(valor.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=config.FUSO)
            _definir_horario(i, local)
            if i["status"] in ("perdido", "erro"): i["status"] = "pendente"; i["tentativas"] = 0; i["erro"] = ""
        elif cmd == "agora":
            local = F.agora_utc().astimezone(config.FUSO).replace(second=0, microsecond=0)
            _definir_horario(i, local)
            if i["status"] != "publicado": i["status"] = "pendente"; i["tentativas"] = 0; i["erro"] = ""
        elif cmd == "legenda":
            if not valor.strip(): raise ValueError("legenda vazia")
            i["legenda"] = valor.strip()
        elif cmd == "titulo":
            if not valor.strip(): raise ValueError("título vazio")
            i["titulo"] = valor.strip()
    return f"{cmd} {iid}" + (f" → {valor.strip()}" if cmd == "mover" else "")

def lote(texto):
    fila = F.carregar()
    ok, falhas = 0, []
    for c in json.loads(texto or "[]"):
        try:
            frase = aplicar(fila, c.get("cmd", ""), c.get("id", ""), c.get("valor", "") or "")
            F.registrar(f"APP {frase}"); ok += 1
        except Exception as e:
            falhas.append(f"{c.get('cmd')} {c.get('id')}: {e}")
            F.registrar(f"APP FALHOU {c.get('cmd')} {c.get('id')} — {e}")
    fila["itens"].sort(key=lambda x: x["quando_utc"])
    F.salvar(fila)
    print(f"{ok} comando(s) aplicado(s)." + (" Falhas: " + "; ".join(falhas) if falhas else ""))

def main(argv=None):
    a = argv or sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]
    if cmd == "lote":
        lote(os.environ.get("COMANDOS", "")); return
    fila = F.carregar()
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
    try:
        frase = aplicar(fila, cmd, a[1], a[2] if len(a) > 2 else "")
    except ValueError as e:
        sys.exit(str(e))
    fila["itens"].sort(key=lambda x: x["quando_utc"])
    F.salvar(fila); F.registrar(f"AJUSTE {frase}")

if __name__ == "__main__":
    main()
