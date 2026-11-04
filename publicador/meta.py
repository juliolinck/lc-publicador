"""Cliente da API oficial da Meta (Instagram Graph API e Páginas do Facebook)."""
import time, requests
from . import config

class ErroMeta(Exception):
    pass

def _checar(r):
    try:
        dados = r.json()
    except Exception:
        raise ErroMeta(f"HTTP {r.status_code}: resposta inválida da Meta")
    if r.status_code >= 400 or "error" in dados:
        e = dados.get("error", {})
        raise ErroMeta(f"{e.get('message', 'erro desconhecido')} (código {e.get('code')}/{e.get('error_subcode')})")
    return dados

def _post(caminho, **params):
    params["access_token"] = config.TOKEN
    return _checar(requests.post(f"{config.GRAPH}/{caminho}", data=params, timeout=120))

def _get(caminho, **params):
    params["access_token"] = config.TOKEN
    return _checar(requests.get(f"{config.GRAPH}/{caminho}", params=params, timeout=60))

def url_midia(rel):
    if not config.MIDIA_URL_BASE:
        raise ErroMeta("MIDIA_URL_BASE não configurado")
    return f"{config.MIDIA_URL_BASE}/{rel}"

def _eh_video(rel):
    return rel.lower().endswith((".mp4", ".mov"))

# ---------------- Instagram ----------------
def _aguardar_container(cid):
    limite = time.time() + config.ESPERA_VIDEO_SEG
    while True:
        st = _get(cid, fields="status_code,status").get("status_code")
        if st in ("FINISHED", "PUBLISHED"):
            return
        if st in ("ERROR", "EXPIRED"):
            det = _get(cid, fields="status").get("status", "")
            raise ErroMeta(f"a Meta recusou a mídia ({st}): {det}")
        if time.time() > limite:
            raise ErroMeta("tempo esgotado esperando a Meta processar o vídeo")
        time.sleep(config.INTERVALO_CONSULTA_SEG)

def _publicar_container(cid):
    _aguardar_container(cid)
    mid = _post(f"{config.IG_ID}/media_publish", creation_id=cid)["id"]
    try:
        link = _get(mid, fields="permalink").get("permalink", "")
    except ErroMeta:
        link = ""
    return {"id": mid, "link": link}

def instagram(item):
    if not (config.TOKEN and config.IG_ID):
        raise ErroMeta("META_TOKEN ou IG_USER_ID não configurados")
    tipo, arqs, leg = item["tipo"], item["arquivos"], item.get("legenda", "")
    ig = config.IG_ID
    if tipo == "reel":
        extra = {"cover_url": url_midia(item["capa"])} if item.get("capa") else {}
        cid = _post(f"{ig}/media", media_type="REELS", video_url=url_midia(arqs[0]), caption=leg, share_to_feed="true", **extra)["id"]
    elif tipo == "imagem":
        cid = _post(f"{ig}/media", image_url=url_midia(arqs[0]), caption=leg)["id"]
    elif tipo == "story":
        if _eh_video(arqs[0]):
            cid = _post(f"{ig}/media", media_type="STORIES", video_url=url_midia(arqs[0]))["id"]
        else:
            cid = _post(f"{ig}/media", media_type="STORIES", image_url=url_midia(arqs[0]))["id"]
    elif tipo == "carrossel":
        filhos = []
        for a in arqs[:10]:
            if _eh_video(a):
                f = _post(f"{ig}/media", media_type="VIDEO", video_url=url_midia(a), is_carousel_item="true")["id"]
            else:
                f = _post(f"{ig}/media", image_url=url_midia(a), is_carousel_item="true")["id"]
            _aguardar_container(f)
            filhos.append(f)
        cid = _post(f"{ig}/media", media_type="CAROUSEL", children=",".join(filhos), caption=leg)["id"]
    else:
        raise ErroMeta(f"tipo desconhecido: {tipo}")
    return _publicar_container(cid)

# ---------------- Facebook (opcional) ----------------
def facebook(item):
    if not (config.TOKEN and config.FB_PAGINA):
        raise ErroMeta("FB_PAGE_ID não configurado")
    pg, tipo, arqs, leg = config.FB_PAGINA, item["tipo"], item["arquivos"], item.get("legenda", "")
    if tipo == "story":
        return {"id": "", "link": "", "obs": "stories só no Instagram"}
    if tipo == "reel":
        ini = _post(f"{pg}/video_reels", upload_phase="start")
        vid = ini["video_id"]
        up = requests.post(ini.get("upload_url", f"{config.RUPLOAD}/{vid}"),
                           headers={"Authorization": f"OAuth {config.TOKEN}", "file_url": url_midia(arqs[0])}, timeout=300)
        _checar(up)
        _post(f"{pg}/video_reels", upload_phase="finish", video_id=vid, video_state="PUBLISHED", description=leg)
        return {"id": vid, "link": f"https://www.facebook.com/reel/{vid}"}
    if tipo == "imagem":
        r = _post(f"{pg}/photos", url=url_midia(arqs[0]), message=leg)
        return {"id": r.get("post_id") or r.get("id"), "link": ""}
    if tipo == "carrossel":
        fotos = [_post(f"{pg}/photos", url=url_midia(a), published="false")["id"] for a in arqs if not _eh_video(a)]
        params = {"message": leg}
        for k, fid in enumerate(fotos):
            params[f"attached_media[{k}]"] = '{"media_fbid":"%s"}' % fid
        r = _post(f"{pg}/feed", **params)
        return {"id": r.get("id"), "link": ""}
    raise ErroMeta(f"tipo desconhecido: {tipo}")

# ---------------- conta e métricas ----------------
def conta():
    return _get(config.IG_ID, fields="username,followers_count,follows_count,media_count")

def limite_publicacao():
    try:
        d = _get(f"{config.IG_ID}/content_publishing_limit", fields="quota_usage,config")
        return d.get("data", [{}])[0]
    except ErroMeta:
        return {}

def metricas_post(media_id, reel):
    nomes = "reach,likes,comments,saved,shares,views" if reel else "reach,likes,comments,saved,shares"
    try:
        d = _get(f"{media_id}/insights", metric=nomes)
    except ErroMeta:
        try:
            d = _get(f"{media_id}/insights", metric="reach,likes,comments,saved")
        except ErroMeta:
            return {}
    out = {}
    for m in d.get("data", []):
        v = m.get("values", [{}])
        out[m["name"]] = v[0].get("value") if v else m.get("total_value", {}).get("value")
    return out
