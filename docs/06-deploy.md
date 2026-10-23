# Deploy: Vercel + Supabase

Produção roda na **Vercel** (Django como função Python) com banco e arquivos no
**Supabase**: Postgres no schema `django` e anexos num bucket privado do
Storage. Decisões e critérios na spec 015.

```
Navegador ──► Vercel ── api/index.py (WSGI do Django) ──┬─► Supabase Postgres (schema django, usuário django_app)
                │                                        └─► Supabase Storage (bucket privado anexos-django)
                └── Vercel Cron ─► /cron/arquivar (diário, 03:00 de Brasília)
```

## Por que assim

| Restrição | Solução |
| --- | --- |
| A API do Supabase expõe o schema `public` com a chave anônima | Tabelas do Django no schema `django`, usuário próprio (`django_app`), sem acesso para `anon`/`authenticated`. O check `ocorrencias.E001` barra o `migrate` fora desse schema. |
| A Vercel não tem disco persistente | Anexos no Supabase Storage (bucket **privado**). A view `/anexos/<id>` confere a permissão e redireciona para uma URL assinada de 60 s. |
| Corpo da requisição limitado a 4,5 MB | Fotos reduzidas no navegador antes do envio (até 1600 px, JPEG 80%) e `UPLOAD_MAX_TOTAL_MB=4`. O navegador e o servidor conferem a soma. |
| Função sem servidor: conexões curtas | Pooler do Supabase em modo transação (porta 6543), sem prepared statements nem cursores no servidor. |
| Sem processo contínuo | Vercel Cron chama `/cron/arquivar`, protegida por `CRON_SECRET`. |
| Sem etapa de build | WhiteNoise serve `static/` direto das pastas (sem `collectstatic`). |

## Passo a passo (primeira vez)

### 1. Supabase

1. Abra o projeto no Supabase, vá em **SQL Editor** e rode
   [`deploy/supabase.sql`](../deploy/supabase.sql), **trocando a senha** do
   `django_app` antes. Guarde a senha.
2. Confira o resultado das duas consultas no fim do script: schema `django` com
   dono `django_app` e bucket `anexos-django` com `public = false`.
3. **Project Settings → Storage → S3 Connection**: anote o *Endpoint* e a
   *Region*. Em **S3 Access Keys**, crie uma chave e anote o *Access key ID* e o
   *Secret access key* (só aparecem uma vez).
4. **Connect** (botão no topo): anote o *project ref* e o host do **Transaction
   pooler** (porta 6543).

As chaves S3 dão acesso total ao Storage: elas ficam só nas variáveis de
ambiente da Vercel e no seu `.env`, nunca no código nem no chat.

### 2. Banco: migrations e primeiro admin (na sua máquina)

As migrations rodam **manualmente**, pela conexão direta (porta 5432):

```bash
# .env local, temporariamente apontando para o Supabase:
#   DATABASE_URL=postgresql://django_app:<senha>@db.<ref>.supabase.co:5432/postgres
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser
```

Se o `migrate` acusar `ocorrencias.E001`, a conexão não está no schema
`django`: confira se o usuário é o `django_app`. Depois, volte o `.env` para o
banco local.

Em deploys futuros, rode `migrate` assim **antes** do deploy sempre que houver
migration nova (o CI acusa quando falta gerar uma).

### 3. Vercel

1. **Add New → Project** e importe o repositório `kayque-ctrl/portal-sac`.
   Framework: *Other*. Sem build command nem output directory.
2. Em **Settings → Environment Variables** (ambiente *Production*):

   | Variável | Valor |
   | --- | --- |
   | `DJANGO_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `DJANGO_DEBUG` | `false` |
   | `DJANGO_ALLOWED_HOSTS` | `portal-sac.vercel.app` (o domínio do projeto) |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://portal-sac.vercel.app` |
   | `SITE_URL` | `https://portal-sac.vercel.app` |
   | `DATABASE_URL` | `postgresql://django_app.<ref>:<senha>@<host-do-pooler>:6543/postgres` |
   | `DB_SCHEMA` | `django` |
   | `STORAGE_BACKEND` | `supabase` |
   | `SUPABASE_S3_ENDPOINT` | `https://<ref>.supabase.co/storage/v1/s3` |
   | `SUPABASE_S3_BUCKET` | `anexos-django` |
   | `SUPABASE_S3_KEY` / `SUPABASE_S3_SECRET` | chaves do passo 1.3 |
   | `SUPABASE_S3_REGION` | região do passo 1.3 (ex.: `sa-east-1`) |
   | `UPLOAD_MAX_TOTAL_MB` | `4` |
   | `CRON_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM` | opcional (sem eles, e-mails não saem) |

   O endereço único de cada deploy e o da branch (`VERCEL_URL` e
   `VERCEL_BRANCH_URL`, que a Vercel define sozinha) entram em
   `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` automaticamente.

3. **Deploy**. O `vercel.json` já reescreve todas as rotas para o Django e
   registra o cron diário.

### 4. Roteiro de teste da homologação

- [ ] `/` e `/login` abrem com estilo (CSS e JS carregados).
- [ ] Login com o admin; `/operacao/` abre.
- [ ] Criar uma empresa e convidar um cliente (sem SMTP, use "Reenviar convite"
      depois de configurar o e-mail, ou crie o cliente pelo `/admin`).
- [ ] Como cliente: abrir ocorrência de **avaria com foto de celular** (> 4 MB
      original), conferir que enviou e que a foto abre no detalhe.
- [ ] Baixar o anexo: a URL final é do Supabase e expira; logado como cliente
      de outra empresa, `/anexos/<id>` dá 404.
- [ ] Operação responde, muda status; cliente aprova.
- [ ] Painel e exportação Excel.
- [ ] No Supabase, **Table Editor**: o schema `public` não ganhou tabelas novas.
- [ ] Na Vercel, **Settings → Cron Jobs**: `/cron/arquivar` listado; "Run" responde
      `{"arquivadas": N}`.

## Depois da virada

O projeto Supabase também tem as tabelas, funções, policies, cron e o bucket
`anexos` do app antigo (Next.js). Como o antigo só tinha dados de teste, eles
podem ser removidos, mas só **depois** de a homologação passar, e com um script
revisado antes de rodar (ver spec 015, item de limpeza).

## Problemas comuns

| Sintoma | Causa provável |
| --- | --- |
| 500 logo ao abrir, log com `ImproperlyConfigured: Defina DJANGO_SECRET_KEY` | chave ausente ou curta com `DJANGO_DEBUG=false` |
| `DisallowedHost` | domínio próprio fora de `DJANGO_ALLOWED_HOSTS` (os endereços `*.vercel.app` do deploy já entram sozinhos) |
| 500 só em algumas telas depois de um deploy, `column ... does not exist` | migration nova não rodada no Supabase: rode o `migrate` do passo 2 |
| 500 logo ao abrir, `No module named 'django'` | existe um `pyproject.toml`: a Vercel instala as dependências dele no lugar do `requirements.txt` |
| 403 CSRF ao enviar formulário | `DJANGO_CSRF_TRUSTED_ORIGINS` sem o `https://` do domínio |
| `prepared statement ... already exists` | `DATABASE_URL` fora da porta 6543 do pooler, ou pooler em modo sessão |
| `relation ... does not exist` | migrations não aplicadas, ou conexão com outro usuário (fora do schema `django`) |
| Erro 413 ao enviar anexos | `UPLOAD_MAX_TOTAL_MB` acima de 4 |
| Anexo abre `AccessDenied` | URL assinada expirou (60 s): recarregue a página e clique de novo |
