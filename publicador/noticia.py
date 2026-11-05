"""Notícia do dia: carrossel de 3 telas a partir de uma notícia sobre dívidas com bancos e financeiras.

Uso:
  python -m publicador.noticia criar noticia.json [--quando "05/11/2026 14:00"] [--seco]
  python -m publicador.noticia banco            # mostra o banco de notícias guardadas
  python -m publicador.noticia limpar-banco     # tira do banco o que tem mais de 7 dias

noticia.json:
{
 "titulo": "título interno curto",
 "url": "https://...", "fonte": "Valor Econômico", "data": "AAAA-MM-DD",
 "tela1": {"chapeu": "NOTÍCIA", "manchete": "...", "linha_fina": "..."},
 "tela2": {"titulo": "O que aconteceu", "texto": "..."},
 "tela3": {"titulo": "O que muda para você", "texto": "..."},
 "legenda": "texto da legenda com hashtags"
}

Regras:
- Um carrossel de notícia por dia, às 14h (Brasília). Sem --quando, usa o primeiro dia livre
  a partir de hoje (hoje só se ainda faltar mais de 1 hora para as 14h).
- Uma notícia só pode ir ao ar até 7 dias depois da data dela.
- A URL da notícia vai para noticias.json (banco), para não repetir a mesma notícia.
"""
import argparse, json, os, sys, textwrap
from datetime import datetime, timedelta, date, time as dtime, timezone
from PIL import Image, ImageDraw, ImageFont
from . import config, fila as F

HORA = dtime(14, 0)
VALIDADE_DIAS = 7
BANCO = os.path.join(config.RAIZ, "noticias.json")
FONTES = os.path.join(os.path.dirname(__file__), "fontes")
W, H = 1080, 1350
MARROM = (74, 51, 37)
CREME = (244, 236, 223)
OURO = (170, 132, 80)
TEXTO_ESCURO = (76, 54, 40)
CREME_SUAVE = (226, 214, 198)

def fonte(nome, tam, peso=None):
    f = ImageFont.truetype(os.path.join(FONTES, nome), tam)
    if peso:
        try: f.set_variation_by_name(peso)
        except Exception: pass
    return f

def serif(t, peso="Bold"): return fonte("PlayfairDisplay.ttf", t, peso)
def sans(t, peso="Regular"): return fonte(f"Inter-{peso}.otf", t)

def quebrar(d, texto, f, largura):
    linhas = []
    for par in texto.split("\n"):
        atual = ""
        for p in par.split():
            teste = (atual + " " + p).strip()
            if d.textlength(teste, font=f) <= largura: atual = teste
            else:
                if atual: linhas.append(atual)
                atual = p
        linhas.append(atual)
    return linhas

def bloco(d, xy, texto, f, cor, largura, entre=1.25):
    x, y = xy
    alt = f.size * entre
    for k, par in enumerate(texto.split("\n")):
        if k: y += alt * 0.5
        for l in quebrar(d, par, f, largura):
            d.text((x, y), l, font=f, fill=cor); y += alt
    return y

def caber(d, texto, gerar_fonte, largura, max_linhas, tam, minimo):
    while tam > minimo:
        f = gerar_fonte(tam)
        if len(quebrar(d, texto, f, largura)) <= max_linhas: return f
        tam -= 4
    return gerar_fonte(minimo)

def moldura(d, escuro, n, total):
    cor = CREME if escuro else TEXTO_ESCURO
    suave = CREME_SUAVE if escuro else (140, 118, 100)
    d.ellipse((80, 74, 152, 146), outline=cor, width=2)
    lc = serif(30, "SemiBold"); tw = d.textlength("LC", font=lc)
    d.text((116 - tw / 2, 92), "LC", font=lc, fill=cor)
    d.text((176, 99), "A S S E S S O R I A", font=sans(22, "SemiBold"), fill=cor)
    num = f"{n}/{total}"; f = sans(22); d.text((W - 80 - d.textlength(num, font=f), 99), num, font=f, fill=suave)
    d.text((80, H - 105), "@lcassessoriabancaria", font=sans(24), fill=suave)
    seta = "Arraste para o lado →" if n < total else ""
    if seta: d.text((W - 80 - d.textlength(seta, font=sans(24)), H - 105), seta, font=sans(24), fill=suave)

def tela1(n, dados, fonte_txt):
    im = Image.new("RGB", (W, H), MARROM); d = ImageDraw.Draw(im); moldura(d, True, 1, 3)
    larg = W - 160
    mf = caber(d, dados["manchete"], lambda t: serif(t), larg, 5, 92, 60)
    linhas = quebrar(d, dados["manchete"], mf, larg)
    lf = sans(38)
    alt_total = 60 + len(linhas) * mf.size * 1.15 + 30 + len(quebrar(d, dados.get("linha_fina", ""), lf, larg)) * 38 * 1.35
    y = max(300, (H - alt_total) / 2)
    d.text((80, y), dados.get("chapeu", "NOTÍCIA").upper(), font=sans(24, "SemiBold"), fill=OURO)
    y += 60
    y = bloco(d, (80, y), dados["manchete"], mf, CREME, larg, 1.15) + 30
    if dados.get("linha_fina"): y = bloco(d, (80, y), dados["linha_fina"], lf, CREME_SUAVE, larg, 1.35)
    d.text((80, H - 175), fonte_txt, font=sans(22), fill=CREME_SUAVE)
    return im

def tela2(dados, n=2, total=3, escuro=False):
    im = Image.new("RGB", (W, H), MARROM if escuro else CREME); d = ImageDraw.Draw(im); moldura(d, escuro, n, total)
    cor, larg = (CREME if escuro else TEXTO_ESCURO), W - 160
    tf = caber(d, dados["titulo"], lambda t: serif(t), larg, 3, 64, 48)
    xf = caber(d, dados["texto"], lambda t: sans(t), larg, 14, 40, 30)
    alt = len(quebrar(d, dados["titulo"], tf, larg)) * tf.size * 1.15 + 36 + len(quebrar(d, dados["texto"], xf, larg)) * xf.size * 1.4
    y = max(230, (H - alt) / 2 - 20)
    d.line((80, y - 40, 140, y - 40), fill=OURO, width=4)
    y = bloco(d, (80, y), dados["titulo"], tf, cor, larg, 1.15) + 36
    bloco(d, (80, y), dados["texto"], xf, cor, larg, 1.4)
    if not escuro: d.line((80, H - 135, W - 80, H - 135), fill=(214, 200, 182), width=2)
    return im

def tela3(dados):
    im = tela2(dados, 3, 3, escuro=True); d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 80, H - 290, W - 80, H - 150
    d.rounded_rectangle((x0, y0, x1, y1), radius=14, outline=OURO, width=2)
    d.text((x0 + 30, y0 + 26), "D I A G N Ó S T I C O   P E L O   W H A T S A P P", font=sans(19, "Medium"), fill=CREME_SUAVE)
    d.text((x0 + 30, y0 + 62), "51 99421-3716", font=serif(46), fill=CREME)
    f = sans(22)
    for k, t in enumerate(("link", "na bio")):
        d.text((x1 - 30 - d.textlength(t, font=f), y0 + 58 + k * 28), t, font=f, fill=CREME_SUAVE)
    return im

def carregar_banco():
    if os.path.exists(BANCO):
        return json.load(open(BANCO, encoding="utf-8"))
    return {"usadas": [], "guardadas": []}

def salvar_banco(b):
    json.dump(b, open(BANCO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def proximo_dia_livre(itens):
    agora = F.agora_utc().astimezone(config.FUSO)
    ocupados = {i["quando_local"][:10] for i in itens if i["id"].startswith("N")}
    d = agora.date()
    if datetime.combine(d, HORA, config.FUSO) - agora < timedelta(hours=1): d += timedelta(days=1)
    while d.strftime("%d/%m/%Y") in ocupados: d += timedelta(days=1)
    return datetime.combine(d, HORA, config.FUSO)

def criar(caminho, quando_txt=None, seco=False):
    n = json.load(open(caminho, encoding="utf-8"))
    for k in ("titulo", "url", "fonte", "data", "tela1", "tela2", "tela3", "legenda"):
        if not n.get(k): sys.exit(f"ERRO: falta o campo {k}")
    fila = F.carregar(); itens = fila["itens"]; banco = carregar_banco()
    if n["url"] in [u["url"] for u in banco["usadas"]]: sys.exit("ERRO: esta notícia já foi usada")
    quando = (datetime.strptime(quando_txt, "%d/%m/%Y %H:%M").replace(tzinfo=config.FUSO) if quando_txt else proximo_dia_livre(itens))
    data_noticia = date.fromisoformat(n["data"])
    if quando.date() - data_noticia > timedelta(days=VALIDADE_DIAS):
        sys.exit(f"ERRO: a notícia é de {data_noticia:%d/%m} e iria ao ar em {quando:%d/%m}, mais de {VALIDADE_DIAS} dias depois")
    nums = [int(i["id"][1:]) for i in itens if i["id"][:1] == "N" and i["id"][1:].isdigit()] + [int(u.get("id", "N0")[1:] or 0) for u in banco["usadas"]]
    pid = f"N{(max(nums) if nums else 0) + 1:03d}"
    fonte_txt = f"Fonte: {n['fonte']}, {data_noticia:%d/%m/%Y}"
    telas = [tela1(1, n["tela1"], fonte_txt), tela2(n["tela2"]), tela3(n["tela3"])]
    legenda = n["legenda"].rstrip()
    if n["url"] not in legenda and n["fonte"] not in legenda:
        legenda += f"\n\nFonte: {n['fonte']} ({data_noticia:%d/%m/%Y})."
    if seco:
        pasta = os.path.join(config.RAIZ, "previa_" + pid)
    else:
        pasta = os.path.join(config.MIDIA, pid)
    os.makedirs(pasta, exist_ok=True)
    arqs = []
    for k, im in enumerate(telas, 1):
        p = os.path.join(pasta, f"0{k}.jpg"); im.save(p, quality=92); arqs.append(os.path.relpath(p, config.RAIZ).replace(os.sep, "/"))
    if seco:
        print(f"prévia em {pasta} para {quando:%d/%m/%Y %H:%M}"); return
    itens.append(dict(id=pid, titulo=n["titulo"], tipo="carrossel", quando_utc=quando.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      quando_local=quando.strftime("%d/%m/%Y %H:%M"), arquivos=arqs, capa="", legenda=legenda,
                      validar_juridico=False, status="pendente", tentativas=0, resultado={}, erro=""))
    itens.sort(key=lambda i: i["quando_utc"]); F.salvar(fila)
    banco["usadas"].append(dict(id=pid, url=n["url"], titulo=n["titulo"], data=n["data"], ao_ar=quando.strftime("%d/%m/%Y %H:%M")))
    banco["guardadas"] = [g for g in banco["guardadas"] if g.get("url") != n["url"]]
    salvar_banco(banco)
    F.registrar(f"AJUSTE notícia {pid} agendada para {quando:%d/%m %H:%M} — {n['titulo']}")

def limpar_banco():
    b = carregar_banco(); hoje = F.agora_utc().astimezone(config.FUSO).date()
    antes = len(b["guardadas"])
    b["guardadas"] = [g for g in b["guardadas"] if hoje - date.fromisoformat(g["data"]) <= timedelta(days=VALIDADE_DIAS)]
    salvar_banco(b); print(f"guardadas: {len(b['guardadas'])} (removidas {antes - len(b['guardadas'])})")

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("criar"); c.add_argument("json"); c.add_argument("--quando"); c.add_argument("--seco", action="store_true")
    sub.add_parser("banco"); sub.add_parser("limpar-banco")
    a = ap.parse_args()
    if a.cmd == "criar": criar(a.json, a.quando, a.seco)
    elif a.cmd == "banco": print(json.dumps(carregar_banco(), ensure_ascii=False, indent=1))
    else: limpar_banco()

if __name__ == "__main__":
    main()
