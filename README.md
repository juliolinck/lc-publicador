# LC Publicador

Programa próprio da LC Assessoria para publicar o calendário no Instagram (@lcassessoriabancaria) sozinho, de graça, pela API oficial da Meta.

- Roda no GitHub, na nuvem. Um despertador fica acordado e dispara a publicação no minuto de cada post. O computador pode ficar desligado.
- Publica Reels (com capa), carrosséis, posts de imagem e stories. A Página do Facebook é opcional.
- Importa de uma vez a planilha do calendário e os zips das postagens.
- Tenta de novo sozinho quando a Meta falha (até 3 vezes).
- Tem um painel com o calendário, o status de cada post e os seguidores rumo à meta.

## Como funciona

1. A planilha e os arquivos entram na pasta `entrada/`.
2. O GitHub importa tudo para a fila (`fila.json`) e guarda as mídias em `midia/`.
3. O workflow Despertador olha a fila a cada minuto e, quando um post chega na hora, dispara o Publicar, que publica e grava o resultado. O agendamento do próprio GitHub (a cada 10 minutos) fica só como reserva, porque ele atrasa horas ou deixa de rodar em repositórios com pouca atividade.
4. Todo dia de manhã, coleta os seguidores e os números de cada post.
5. O painel fica em `https://SEU-USUARIO.github.io/lc-publicador/`.

## Instalação (uma vez só, cerca de 40 minutos)

Os nomes dos menus do GitHub e da Meta mudam de vez em quando. Se algo não bater, peça ao Claude para guiar na tela.

### 1. GitHub

1. Crie uma conta gratuita em github.com.
2. Crie um repositório **público** chamado `lc-publicador`. O plano gratuito só publica o painel e as mídias de repositórios públicos, e as postagens vão ficar públicas no Instagram de qualquer forma.
3. Suba todos os arquivos deste projeto para o repositório. O caminho mais fácil é pedir ao Claude, depois de conectar o GitHub ao Claude.
4. Em **Settings > Pages**, escolha "Deploy from a branch", branch `main`, pasta `/ (root)`, e salve. Anote o endereço que aparece (`https://SEU-USUARIO.github.io/lc-publicador`).

### 2. App da Meta (gratuito)

1. Entre em developers.facebook.com com o Facebook que administra a Página "LC Assessoria" e crie um app do tipo empresa. Você fica como administrador; para publicar só na própria conta, em geral não é preciso enviar o app para revisão.
2. Abra o **Graph API Explorer**, escolha o seu app e gere um token de usuário com estas permissões:
   `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`, `business_management` (e `pages_manage_posts`, se quiser publicar também no Facebook).
3. Abra o **Access Token Debugger**, cole esse token e clique em "Extend Access Token" para gerar o token de longa duração.
4. No Graph API Explorer, usando o token de longa duração, consulte:
   `me/accounts?fields=name,id,access_token,instagram_business_account`
   Na linha da Página "LC Assessoria", anote:
   - `access_token`: o token da Página, que não expira;
   - `id`: o id da Página;
   - `instagram_business_account.id`: o id do Instagram.

### 3. Guardar as chaves no GitHub

No repositório, abra **Settings > Secrets and variables > Actions**.

- Em **Secrets** (ficam ocultos):
  - `META_TOKEN`: o token da Página;
  - `IG_USER_ID`: o id do Instagram;
  - `FB_PAGE_ID`: o id da Página.
- Em **Variables**:
  - `MIDIA_URL_BASE`: o endereço do passo 1.4, sem barra no final;
  - `PUBLICAR_FACEBOOK`: `nao` (ou `sim` para publicar também na Página).

O token é como uma senha: cole só nesses campos e não mande por e-mail ou mensagem.

### 4. Ligar a automação

Na aba **Actions**, se o GitHub pedir, clique para ativar os workflows. Depois abra "Publicar" e clique em "Run workflow" para um primeiro teste. Se não houver nada na hora, ele só responde "Nada para publicar agora".

## Uso no dia a dia

**Subir um mês novo:** em `entrada/`, use "Add file > Upload files" e solte a planilha (.xlsx) e os zips das semanas. O GitHub importa sozinho em cerca de 1 minuto e limpa a pasta. Pelo navegador, cada arquivo pode ter no máximo 25 MB: um zip maior precisa ser descompactado e enviado como pasta, ou subido pelo Claude.

A planilha precisa da aba "Calendário" com o cabeçalho na linha 4 e as colunas Data, Horário, Formato, Título, Arquivo e Legenda pronta. É o mesmo modelo de LC-calendario-e-legendas.xlsx.

**Acompanhar:** abra o painel. Cada post mostra o status (na fila, publicado, erro, perdido ou pausado) e o link do post publicado. O histórico completo fica em `registro.log`.

**Ajustes:** peça ao Claude ou rode no terminal:
```
python -m publicador.gerenciar listar --pendentes
python -m publicador.gerenciar pausar R10
python -m publicador.gerenciar retomar R10
python -m publicador.gerenciar mover R10 "15/11/2026 19:00"
python -m publicador.gerenciar repetir R10
python -m publicador.gerenciar remover R10
python -m publicador.gerenciar limpar 7
```
`repetir` vale para um post com erro ou perdido; `limpar` apaga as mídias de posts publicados há mais de 7 dias.

## Regras do robô

- Publica no horário marcado. O GitHub pode atrasar alguns minutos nos horários de pico.
- Um post que passou mais de 6 horas da hora sem ter sido tentado vira "perdido" e não é publicado atrasado. Para publicar mesmo assim, use `mover`.
- Um post com erro é tentado de novo a cada rodada, até 3 vezes. A mensagem de erro aparece no painel.
- O que já saiu numa rede nunca é publicado de novo, mesmo se a rodada cair no meio.
- Erro "código 190" significa token inválido ou revogado: gere um novo token (passo 2) e troque o segredo `META_TOKEN`.
- O GitHub desliga tarefas agendadas de repositórios sem atividade por 60 dias. As gravações automáticas evitam isso, mas, se o robô ficar parado, reative em Actions.

## Arquivos

| Arquivo | Para quê |
|---|---|
| `publicador/importar.py` | Lê a planilha e os zips e monta a fila |
| `publicador/executar.py` | Publica o que está na hora |
| `publicador/meta.py` | Conversa com a API da Meta |
| `publicador/metricas.py` | Coleta seguidores e números dos posts |
| `publicador/painel.py` | Gera o painel `index.html` |
| `publicador/gerenciar.py` | Ajustes na fila |
| `.github/workflows/` | As tarefas automáticas: Importar, Publicar e Métricas |
| `fila.json` | A fila, com status e resultado de cada post |

## Notícia do dia

Todo dia de manhã, uma tarefa programada do Claude procura notícias sobre dívidas de pessoas e empresas com bancos e financeiras e agenda dois carrosséis de 3 telas, às 11h e às 17h (Brasília), com o código N001, N002 etc.

- `python -m publicador.noticia criar noticia.json [--quando "05/11/2026 11:00"] [--seco]` gera as telas em `midia/Nxxx/` e põe o post na fila no próximo horário livre (`--seco` só gera uma prévia).
- `noticias.json` guarda as notícias já usadas (para não repetir) e as que sobraram num dia de muitas notícias (`guardadas`), que podem ir ao ar até 7 dias depois da data da notícia.
- `python -m publicador.noticia limpar-banco` tira do banco as guardadas com mais de 7 dias.
- As fontes das telas ficam em `publicador/fontes/` (Playfair Display e Inter, licença livre).
