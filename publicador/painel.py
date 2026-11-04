"""Gera o painel (index.html) com calendário, status de cada post e seguidores.

Uso: python -m publicador.painel
"""
import json, os, html
from datetime import datetime
from . import config, fila as F

META_SEGUIDORES = int(os.environ.get("META_SEGUIDORES", "3000"))

PAGINA = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LC Publicador</title>
<style>
:root{--creme:#F4ECDF;--creme2:#EADFCB;--marrom:#4A3324;--marrom2:#7A5A42;--ouro:#A8834F;--ok:#3F7D4E;--erro:#B3412E;--pend:#8A7A66}
*{box-sizing:border-box}body{margin:0;background:var(--creme);color:var(--marrom);font:15px/1.45 -apple-system,Segoe UI,Inter,Arial,sans-serif}
header{background:var(--marrom);color:var(--creme);padding:22px 24px}h1{margin:0;font:600 22px Georgia,serif;letter-spacing:.5px}
header small{opacity:.75}main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:22px}
.card{background:#fff8;border:1px solid var(--creme2);border-radius:12px;padding:14px}.card b{display:block;font:600 26px Georgia,serif}
.barra{height:10px;background:var(--creme2);border-radius:6px;overflow:hidden;margin-top:8px}.barra i{display:block;height:100%;background:var(--ouro)}
h2{font:600 18px Georgia,serif;margin:26px 0 10px}
.filtros{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}.filtros button{border:1px solid var(--marrom2);background:none;color:var(--marrom);border-radius:20px;padding:5px 14px;cursor:pointer}
.filtros button.on{background:var(--marrom);color:var(--creme)}
.dia{background:#fff8;border:1px solid var(--creme2);border-radius:12px;margin-bottom:10px;padding:10px 14px}
.dia h3{margin:0 0 6px;font:600 14px Inter,Arial;color:var(--marrom2);text-transform:capitalize}
.post{display:flex;gap:12px;align-items:center;padding:7px 0;border-top:1px solid var(--creme2)}.post:first-of-type{border-top:0}
.post img{width:44px;height:55px;object-fit:cover;border-radius:6px;background:var(--creme2);flex:none}
.hora{font-variant-numeric:tabular-nums;width:46px;flex:none;font-weight:600}.tit{flex:1;min-width:0}
.tit span{display:block;font-size:12px;color:var(--marrom2)}
.st{font-size:12px;border-radius:12px;padding:2px 10px;white-space:nowrap;color:#fff}
.st.publicado{background:var(--ok)}.st.pendente{background:var(--pend)}.st.erro,.st.perdido{background:var(--erro)}.st.pausado{background:var(--ouro)}
.post a{color:inherit}svg{width:100%;height:120px}
@media (max-width:600px){.post .tit span{display:none}}
</style></head><body>
<header><h1>LC Publicador</h1><small>@lcassessoriabancaria · atualizado em __ATUALIZADO__</small></header>
<main>
<div class="cards" id="cards"></div>
<h2>Seguidores</h2><div class="card"><svg id="graf" viewBox="0 0 600 120" preserveAspectRatio="none"></svg></div>
<h2>Calendário</h2><div class="filtros" id="filtros"></div><div id="cal"></div>
</main>
<script>
const FILA=__FILA__, MET=__MET__, META=__META__;
const st={pendente:'na fila',publicado:'publicado',erro:'erro',perdido:'perdido',pausado:'pausado'};
const tipos={reel:'Reel',carrossel:'Carrossel',imagem:'Post',story:'Story'};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cont=s=>FILA.filter(i=>i.status===s).length;
const seg=(MET.conta||{}).followers_count;
const ini=(MET.seguidores||[])[0]?.total;
document.getElementById('cards').innerHTML=
 `<div class="card">Seguidores<b>${seg??'—'}</b>meta ${META.toLocaleString('pt-BR')}<div class="barra"><i style="width:${seg?Math.min(100,seg/META*100):0}%"></i></div></div>`+
 `<div class="card">Ganho no período<b>${seg!=null&&ini!=null?'+'+(seg-ini):'—'}</b>desde o 1º registro</div>`+
 `<div class="card">Publicados<b>${cont('publicado')}</b>de ${FILA.length}</div>`+
 `<div class="card">Na fila<b>${cont('pendente')}</b>${cont('pausado')} pausado(s)</div>`+
 `<div class="card">Com erro<b>${cont('erro')+cont('perdido')}</b>ver abaixo</div>`;
(function(){const s=MET.seguidores||[];const g=document.getElementById('graf');if(s.length<2){g.outerHTML='<p style="margin:0">O gráfico aparece a partir do 2º dia de coleta.</p>';return}
 const v=s.map(x=>x.total||0),mn=Math.min(...v),mx=Math.max(...v,mn+1);
 const p=v.map((y,i)=>`${i/(v.length-1)*600},${110-(y-mn)/(mx-mn)*100}`).join(' ');
 g.innerHTML=`<polyline fill="none" stroke="#A8834F" stroke-width="3" points="${p}"/>`})();
let filtro='todos';
function render(){
 const dias={};FILA.forEach(i=>{if(filtro!=='todos'&&i.status!==filtro&&!(filtro==='erro'&&i.status==='perdido'))return;
  const d=i.quando_local.slice(0,10);(dias[d]=dias[d]||[]).push(i)});
 const html=Object.keys(dias).map(d=>{const [dd,mm,aa]=d.split('/');const dt=new Date(aa,mm-1,dd);
  const nome=dt.toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'2-digit'});
  return `<div class="dia"><h3>${nome}</h3>`+dias[d].map(i=>{const r=(i.resultado||{}).instagram||{};const m=(MET.posts||{})[i.id]||{};
   const thumb=i.capa||(i.arquivos||[]).find(a=>!/\.(mp4|mov)$/i.test(a))||'';
   const num=m.reach!=null?` · alcance ${m.reach}`+(m.likes!=null?` · ${m.likes} curtidas`:''):'';
   return `<div class="post">${thumb&&!i.arquivos_removidos?`<img src="${esc(thumb)}" loading="lazy" alt="">`:'<img alt="">'}<div class="hora">${i.quando_local.slice(11)}</div>
   <div class="tit">${r.link?`<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(i.titulo)}</a>`:esc(i.titulo)}<span>${tipos[i.tipo]||i.tipo} · ${esc(i.id)}${num}${i.erro?' · '+esc(i.erro):''}</span></div>
   <span class="st ${i.status}">${st[i.status]||i.status}</span></div>`}).join('')+'</div>'}).join('');
 document.getElementById('cal').innerHTML=html||'<p>Nada neste filtro.</p>';
 document.getElementById('filtros').innerHTML=['todos','pendente','publicado','erro','pausado'].map(f=>`<button class="${f===filtro?'on':''}" onclick="filtro='${f}';render()">${f==='todos'?'Todos':st[f]}</button>`).join('');
}
render();
</script></body></html>"""

def gerar():
    fila = F.carregar()["itens"]
    met = json.load(open(config.METRICAS, encoding="utf-8")) if os.path.exists(config.METRICAS) else {}
    leve = [{k: i.get(k) for k in ("id", "titulo", "tipo", "quando_local", "status", "erro", "arquivos", "capa", "resultado", "arquivos_removidos")} for i in fila]
    seguro = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    out = (PAGINA.replace("__FILA__", seguro(leve)).replace("__MET__", seguro(met)).replace("__META__", str(META_SEGUIDORES))
           .replace("__ATUALIZADO__", F.agora_utc().astimezone(config.FUSO).strftime("%d/%m/%Y %H:%M")))
    with open(os.path.join(config.RAIZ, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)
    print("painel gerado: index.html")

if __name__ == "__main__":
    gerar()
