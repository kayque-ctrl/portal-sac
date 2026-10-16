# Arquitetura

## Visão de alto nível

Monólito Django com renderização no servidor. Não há API separada nem SPA:
cada tela é um template Django, e o comportamento no navegador (wizard,
filtros, modais, sino de notificações) é feito com Alpine.js sobre o HTML
que veio do servidor.

```
Navegador ──HTTP──► config/urls.py
                     ├── contas/urls.py        login, convite, senha
                     ├── ocorrencias.urls
                     │     ├── publico_urls    /, /consulta, /anexos/<id>, notificações
                     │     ├── portal_urls     /portal/...
                     │     └── operacao_urls   /operacao/...
                     └── /admin/               Django admin (suporte)
```

## Apps

| App | Responsabilidade |
| --- | --- |
| `contas` | `Usuario` (login por e-mail, `AUTH_USER_MODEL`), `Empresa`, convites e redefinição de senha com tokens de uso único |
| `ocorrencias` | Todo o domínio: ocorrências, itens, mensagens, anexos, histórico, notificações, avisos, contatos, SLA, painéis |

## Camadas dentro de `ocorrencias`

```
views/ (HTTP)
  │  decorators de acesso: cliente_required / operacao_required / admin_required
  │  lê request, chama serviço, renderiza template ou devolve JSON
  ▼
servicos.py (regras de negócio)
  │  valida, aplica regra e devolve Resultado(erro, aviso, dados)
  │  usa permissoes.py para decidir quem pode
  ▼
models.py (persistência + invariantes)
     Ocorrencia.save(por=...) → protocolo, SLA, histórico, notificações
     Mensagem.save()          → notificação de nova mensagem pública
```

Módulos de apoio, sem dependência de request:

| Módulo | Conteúdo |
| --- | --- |
| `labels.py` | Enums (`TextChoices`), rótulos, listas de regra (`CATEGORIAS_EXIGEM_FOTO`…) e classes Tailwind de cor |
| `permissoes.py` | `ocorrencias_visiveis`, `pode_ver`, `pode_agir`, `mensagens_visiveis`, `colegas_da_empresa` |
| `sla.py` | Interpretação do SLA para exibição (no prazo, em risco, vencido, pausado…) |
| `kpis.py` | Cálculo do painel do cliente; funções puras com testes |
| `notificacoes.py` | Notificações in-app (nova ocorrência, mudança de status, nova mensagem) |
| `emails.py` | Layout e envio best-effort de e-mail |
| `planilhas.py` | Importação de itens e exportação `.xlsx` (openpyxl) |
| `uploads.py` | Limites (5 arquivos, 10 MB), tipos aceitos e checagem do conteúdo |
| `formato.py` | Formatação de datas, números e durações |
| `templatetags/` | Filtros e tags usados nos templates (badges, SLA, ícones) |
| `context_processors.py` | Navegação e contador de notificações do cabeçalho |

### Por que as regras ficam no `save()`

No projeto original, protocolo, SLA, histórico de status e notificações
eram **triggers** do Postgres. Em Django, o equivalente mais fiel é o
`save()` do modelo, dentro de `transaction.atomic()`. Consequências:

- **Nunca** altere `status` com `QuerySet.update()` ou `bulk_update()`:
  isso pula SLA, histórico e notificações. Carregue a instância e use
  `ocorrencia.save(por=usuario)`.
- O parâmetro `por` substitui o `auth.uid()` dos triggers: é quem fica
  registrado no histórico e quem não recebe a própria notificação.

## Segurança

| Antes (Supabase) | Agora (Django) |
| --- | --- |
| RLS por linha | `permissoes.py` aplicado em toda view e serviço |
| `is_operador()` / `is_admin()` | `user.eh_operacao` / `user.eh_admin` + decorators |
| Bucket privado + URL assinada | `MEDIA_ROOT` fora do `static`; download só por `/anexos/<id>`, que chama `pode_ver` e esconde anexo de nota interna do cliente |
| `handle_new_user` força papel `cliente` | Convite cria sempre `cliente`; só admin concede `admin` (checado na view de usuários) |
| `generateLink` / `verifyOtp` | `contas/convites.py`: token do Django, uso único, invalida ao definir senha |

Princípios:

- **Leitura ≠ escrita.** `pode_ver` (autor, colega da mesma empresa ou
  operação) e `pode_agir` (autor ou operação) são funções separadas, para
  que ampliar a leitura nunca amplie a escrita por acidente.
- **Esconder no template não basta.** Toda ação é revalidada no servidor;
  os testes em `tests/test_views.py` fazem a requisição direta.
- **Respostas 404 para o que o usuário não pode ver**, em vez de 403, para
  não revelar que o recurso existe.
- **Esqueci a senha não revela** se o e-mail está cadastrado.
- **Id vindo de formulário nunca vai cru para o banco.** Use `uuids_validos`
  (em `views/comum.py`) ou trate `ValidationError`: `filter(pk="lixo")` num
  campo UUID levanta exceção e vira erro 500. As rotas com `<uuid:pk>` já são
  protegidas pelo próprio roteamento.
- **CSRF** em todos os formulários e nas chamadas `fetch` (`postForm` em
  `app.js` envia `X-CSRFToken`).

## Front-end

- **Sem build.** Tailwind v4 (script de navegador), Alpine.js, Lucide e
  Chart.js vêm de CDN, com versão fixa. Em produção, o recomendado é
  compilar o Tailwind com `@tailwindcss/cli`.
- `static/js/app.js` reúne os componentes Alpine (`Alpine.data(...)`):
  wizard de nova ocorrência, filtros do portal, painel de avisos,
  notificações, modais. Equivale aos componentes `"use client"` do React.
- `templates/partials/` tem os blocos reutilizáveis (modal, paginação,
  stat card, campo de senha, tema claro/escuro).
- **Sistema visual "Balcão"** em `static/css/sac.css` (spec 022): tokens de
  cor no `:root` (e em `.dark`) e os componentes (`.btn`, `.card`, `.in`,
  `.campo`, `.pill`, `.seg`, `.tbl`, `.tl-*` da linha do tempo, `.sb` do menu
  lateral, `.tb` da barra de baixo do celular). As cores da marca estão em
  preto e branco; a paleta verde e cobre do desenho entra trocando só os
  valores marcados com "verde e cobre:". Fontes: Bricolage Grotesque e DM
  Mono. Tailwind fica para layout (grid, espaçamento, `md:`).
- **Casca** (`templates/area.html`): menu lateral no computador e, no
  celular, cabeçalho + barra de baixo com "Mais"/"Conta" numa folha. O menu
  vem de `context_processors.cabecalho`. Telas públicas usam
  `partials/centralizado.html` (faixa da marca + cartão do formulário).
- Classes de cor de status, prioridade e categoria vêm de `labels.py` via
  template tags; não escreva essas classes à mão nos templates.
- Tema claro/escuro por classe `dark`, com a preferência guardada no
  navegador.

## Dados e ambiente

- `.env` lido com `python-dotenv`. Sem `.env`: `DEBUG`, SQLite e e-mail no
  console.
- Configuração por ambiente em [config/ambiente.py](../config/ambiente.py):
  funções puras (banco, storage, segurança, e-mail, limite de upload) chamadas
  pelo `settings.py` e testadas em `tests/unit/test_ambiente.py`.
- Banco: `DATABASE_URL` (Postgres do Supabase, schema `django`, usuário
  `django_app`); sem ela, SQLite. O check `ocorrencias.E001` barra o `migrate`
  fora do schema esperado.
- Anexos: `STORAGE_BACKEND=supabase` grava num bucket privado; a view de
  download confere a permissão e redireciona para URL assinada de 60 s.
- Produção completa (Vercel + Supabase): [06-deploy.md](06-deploy.md).
- Fuso `America/Sao_Paulo`, idioma `pt-br`.
- Chaves primárias UUID em todas as entidades de negócio.
- Protocolo `AAAA-NNNNNN` gerado por um contador (`ProtocoloSeq`) com
  `select_for_update`, e não por `max()+1`, para não repetir número em
  concorrência.

## Tarefas agendadas

| Comando | Substitui | Frequência sugerida |
| --- | --- | --- |
| `arquivar_concluidas --dias 30` | `pg_cron` da migration 0007 | Diária (local/servidor próprio) |
| `GET /cron/arquivar` (Vercel Cron, `Authorization: Bearer $CRON_SECRET`) | o mesmo, em produção | Diária, 03:00 de Brasília (`vercel.json`) |

## Testes

`pytest` roda a suíte em `tests/`, em quatro camadas (`unit`, `regras`, `http`
e `regressao`), com fixtures em `tests/conftest.py` e dados de entrada em
`tests/builders.py`. O padrão, as convenções e as regras da suíte de regressão
estão em [05-testes.md](05-testes.md).

## De/para com o projeto original

| Next.js / Supabase | Django |
| --- | --- |
| `auth.users` + `profiles` | `contas.Usuario` (login por e-mail, `AUTH_USER_MODEL`) |
| `empresas` | `contas.Empresa` |
| Tabelas `ocorrencias`, `mensagens`, `anexos`… | `ocorrencias/models.py` |
| Triggers (protocolo, SLA, histórico, notificações) | `Ocorrencia.save(por=...)`, `Mensagem.save()`, `notificacoes.py` |
| Sequence `protocolo_seq` | `ProtocoloSeq` com `select_for_update` |
| RLS (`pode_ver_ocorrencia`, `pode_agir_ocorrencia`…) | `permissoes.py` + decorators em `views/comum.py` |
| Server Actions | `servicos.py` (regras) + `views/` (HTTP) |
| `kpis_cliente()` (SQL) + `kpis-cliente.ts` | `kpis.py` |
| `sla.ts`, `labels.ts`, `format.ts`, `uploads.ts` | `sla.py`, `labels.py`, `formato.py`, `uploads.py` |
| Supabase Storage (bucket privado + URL assinada) | Em produção, o mesmo Storage via `django-storages`, com a permissão conferida pela view `/anexos/<id>` antes da URL assinada; em desenvolvimento, `MEDIA_ROOT` |
| `generateLink` / `verifyOtp` | Tokens do Django em `contas/convites.py`, uso único |
| Nodemailer | `django.core.mail` (`emails.py`) |
| ExcelJS | openpyxl (`planilhas.py`) |
| pg_cron (auto-arquivar) | Vercel Cron em `/cron/arquivar` (ou `manage.py arquivar_concluidas`) |
| Componentes React "use client" | Templates Django + Alpine.js (`static/js/app.js`) |
| Nivo (gráficos) | Chart.js no painel da operação; HTML/CSS no painel do cliente |
| `proxy.ts` (middleware de sessão) | Sessão do Django + decorators de acesso |

Não foram migrados: os dados de produção do Supabase (decisão pendente) e
o roadmap de API pública, que continua documentado no repositório original.
