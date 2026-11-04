"""Importa a planilha do calendário e os arquivos das postagens para a fila.

Uso:
  python -m publicador.importar PLANILHA.xlsx ZIP_OU_PASTA [ZIP_OU_PASTA ...] [--so-aprovados] [--desde AAAA-MM-DD] [--substituir]

- Copia as mídias para midia/<ID>/ com nomes simples (01.mp4, 01.png, 02.png...).
- Acrescenta os itens à fila.json (ou substitui a fila inteira com --substituir).
- Itens já presentes (mesmo ID e mesmo horário) não são duplicados.
"""
import sys, os, shutil, zipfile, tempfile, argparse
from datetime import datetime, time as dtime, timezone
import openpyxl
from PIL import Image
from . import config, fila as F

FORMATOS = {"Reel": "reel", "Carrossel": "carrossel", "Post-base (feed)": "imagem", "Post": "imagem", "Imagem": "imagem",
            "Live": "story", "Story": "story"}
HORA_AVISO_LIVE = dtime(10, 0)

def _indice(entradas):
    raizes, temporarios = [], []
    for e in entradas:
        if os.path.isdir(e):
            raizes.append(e)
            for base, _, files in os.walk(e):
                for f in files:
                    p = os.path.join(base, f)
                    if f.lower().endswith(".zip") and zipfile.is_zipfile(p):
                        d = tempfile.mkdtemp(prefix="lc_"); temporarios.append(d)
                        with zipfile.ZipFile(p) as z: z.extractall(d)
                        raizes.append(d)
        elif zipfile.is_zipfile(e):
            d = tempfile.mkdtemp(prefix="lc_"); temporarios.append(d)
            with zipfile.ZipFile(e) as z: z.extractall(d)
            raizes.append(d)
        elif os.path.isfile(e):
            raizes.append(os.path.dirname(os.path.abspath(e)))
        else:
            print(f"AVISO: não encontrado: {e}")
    idx = {}
    for r in raizes:
        for base, dirs, files in os.walk(r):
            for nome in dirs + files:
                idx.setdefault(nome, os.path.join(base, nome))
    return idx, temporarios

def _colunas(ws):
    cab = {}
    for c in ws[4]:
        if c.value: cab[str(c.value).strip().lower()] = c.column - 1
    def i(*nomes):
        for n in nomes:
            for k, v in cab.items():
                if k.startswith(n): return v
    return dict(data=i("data"), hora=i("horário", "horario"), formato=i("formato"), titulo=i("título", "titulo"),
                status=i("status"), arquivo=i("arquivo"), legenda=i("legenda"), nota=i("nota jur"))

def _copiar(src, dst_sem_ext):
    """Copia a mídia. Imagens viram JPEG, o único formato de imagem que a API do Instagram aceita."""
    ext = os.path.splitext(src)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        dst = dst_sem_ext + ".jpg"
        with Image.open(src) as im:
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA"); fundo = Image.new("RGB", im.size, (255, 255, 255))
                fundo.paste(im, mask=im.split()[-1]); im = fundo
            else:
                im = im.convert("RGB")
            im.save(dst, "JPEG", quality=92, optimize=True)
        return dst
    dst = dst_sem_ext + ext
    shutil.copyfile(src, dst)
    return dst

def _id_do_arquivo(nome, linha):
    base = os.path.basename(nome.rstrip("/")).rsplit(".", 1)[0]
    for parte in base.split("_"):
        if len(parte) >= 2 and parte[0] in "RCBL" and parte[1:].isdigit():
            return parte
    return f"L{linha}"

def importar(planilha, entradas, so_aprovados=False, desde=None, substituir=False):
    wb = openpyxl.load_workbook(planilha, data_only=True)
    ws = wb["Calendário"] if "Calendário" in wb.sheetnames else wb.active
    col = _colunas(ws)
    faltam = [k for k, v in col.items() if v is None and k not in ("status", "nota")]
    if faltam: sys.exit(f"ERRO: a planilha não tem as colunas {faltam} na linha 4")
    idx, temporarios = _indice(entradas)
    fila = {"itens": []} if substituir else F.carregar()
    existentes = {(i["id"], i["quando_utc"]) for i in fila["itens"]}
    novos, problemas = 0, []
    agora = F.agora_utc()
    for n, row in enumerate(ws.iter_rows(min_row=5, values_only=True), 5):
        fmt = row[col["formato"]]
        if not fmt: continue
        tipo = FORMATOS.get(str(fmt).strip())
        if not tipo: problemas.append(f"linha {n}: formato desconhecido '{fmt}'"); continue
        status = (row[col["status"]] if col["status"] is not None else "") or ""
        if status == "Publicado": continue
        if so_aprovados and status not in ("Aprovado", "Agendado"): continue
        data = row[col["data"]]
        if not isinstance(data, datetime): problemas.append(f"linha {n}: data inválida"); continue
        if tipo == "story" and str(fmt).strip() == "Live":
            hora = HORA_AVISO_LIVE
        else:
            h = str(row[col["hora"]] or "12:00").split(":")
            hora = dtime(int(h[0]), int(h[1]) if len(h) > 1 else 0)
        local = datetime.combine(data.date(), hora, config.FUSO)
        if desde and local.date() < desde: continue
        arq = str(row[col["arquivo"]] or "").strip()
        nome = os.path.basename(arq.rstrip("/"))
        origem = idx.get(nome)
        if not origem: problemas.append(f"linha {n}: arquivo não encontrado: {nome or '(vazio)'}"); continue
        if os.path.isdir(origem):
            arquivos = sorted(f for f in os.listdir(origem) if f.lower().endswith((".png", ".jpg", ".jpeg", ".mp4", ".mov")))
            fontes = [os.path.join(origem, f) for f in arquivos]
        else:
            fontes = [origem]
        iid = _id_do_arquivo(arq, n)
        qutc = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if (iid, qutc) in existentes: continue
        destino = os.path.join(config.MIDIA, iid)
        os.makedirs(destino, exist_ok=True)
        rel = []
        for k, src in enumerate(fontes, 1):
            dst = _copiar(src, os.path.join(destino, f"{k:02d}"))
            rel.append(os.path.relpath(dst, config.RAIZ).replace(os.sep, "/"))
        capa = ""
        if tipo == "reel":
            cand = os.path.join(os.path.dirname(origem), os.path.basename(origem).rsplit(".", 1)[0] + "_capa.png")
            if os.path.exists(cand):
                capa = os.path.relpath(_copiar(cand, os.path.join(destino, "capa")), config.RAIZ).replace(os.sep, "/")
        if tipo == "carrossel" and not (2 <= len(rel) <= 10):
            problemas.append(f"linha {n}: carrossel precisa de 2 a 10 imagens (tem {len(rel)})")
        legenda = (row[col["legenda"]] or "") if col["legenda"] is not None else ""
        if len(legenda) > 2200: problemas.append(f"linha {n}: legenda passa de 2.200 caracteres")
        if local.astimezone(timezone.utc) < agora: problemas.append(f"linha {n} ({iid}): horário já passou")
        fila["itens"].append(dict(
            id=iid, titulo=str(row[col["titulo"]] or ""), tipo=tipo, quando_utc=qutc,
            quando_local=local.strftime("%d/%m/%Y %H:%M"), arquivos=rel, capa=capa, legenda=legenda,
            validar_juridico=bool(col["nota"] is not None and row[col["nota"]]),
            status="pendente", tentativas=0, resultado={}, erro=""))
        existentes.add((iid, qutc)); novos += 1
    fila["itens"].sort(key=lambda i: i["quando_utc"])
    F.salvar(fila)
    for t in temporarios: shutil.rmtree(t, ignore_errors=True)
    print(f"{novos} itens novos na fila; total {len(fila['itens'])}.")
    if problemas:
        print(f"{len(problemas)} problema(s):"); [print(" -", p) for p in problemas]
    return novos, problemas

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("planilha"); ap.add_argument("entradas", nargs="+")
    ap.add_argument("--so-aprovados", action="store_true")
    ap.add_argument("--desde", help="AAAA-MM-DD")
    ap.add_argument("--substituir", action="store_true")
    a = ap.parse_args()
    desde = datetime.fromisoformat(a.desde).date() if a.desde else None
    importar(a.planilha, a.entradas, a.so_aprovados, desde, a.substituir)

if __name__ == "__main__":
    main()
