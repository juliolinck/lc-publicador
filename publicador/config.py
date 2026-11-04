"""Configuração lida das variáveis de ambiente (no GitHub: Settings > Secrets and variables > Actions)."""
import os
from datetime import timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILA = os.path.join(RAIZ, "fila.json")
METRICAS = os.path.join(RAIZ, "metricas.json")
MIDIA = os.path.join(RAIZ, "midia")
PAINEL = os.path.join(RAIZ, "docs")
REGISTRO = os.path.join(RAIZ, "registro.log")

FUSO = timezone(timedelta(hours=-3))  # America/Sao_Paulo, sem horário de verão desde 2019

GRAPH_VERSAO = os.environ.get("GRAPH_VERSAO", "v23.0")
GRAPH = os.environ.get("GRAPH_URL", f"https://graph.facebook.com/{GRAPH_VERSAO}")
RUPLOAD = os.environ.get("RUPLOAD_URL", f"https://rupload.facebook.com/video-upload/{GRAPH_VERSAO}")

TOKEN = os.environ.get("META_TOKEN", "")          # token de Página (longa duração)
IG_ID = os.environ.get("IG_USER_ID", "")          # id da conta profissional do Instagram
FB_PAGINA = os.environ.get("FB_PAGE_ID", "")      # id da Página do Facebook (opcional)
PUBLICAR_FACEBOOK = os.environ.get("PUBLICAR_FACEBOOK", "nao").lower() in ("sim", "1", "true", "yes")

# Endereço público onde a pasta midia/ fica acessível (a Meta baixa as mídias por URL).
# No GitHub: https://raw.githubusercontent.com/USUARIO/REPOSITORIO/main
MIDIA_URL_BASE = (os.environ.get("MIDIA_URL_BASE") or "https://juliolinck.github.io/lc-publicador").rstrip("/")

MAX_TENTATIVAS = int(os.environ.get("MAX_TENTATIVAS", "3"))
ATRASO_MAXIMO_HORAS = float(os.environ.get("ATRASO_MAXIMO_HORAS", "6"))  # passou disso, não publica e marca "perdido"
ESPERA_VIDEO_SEG = int(os.environ.get("ESPERA_VIDEO_SEG", "600"))
INTERVALO_CONSULTA_SEG = float(os.environ.get("INTERVALO_CONSULTA_SEG", "10"))
