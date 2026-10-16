# Portal de Ocorrências — Django

Sistema para que **empresas clientes** registrem e acompanhem problemas de
pedidos e notas fiscais (avarias, faltas, sobras, trocas de volume, produtos
vencidos, atrasos, reclamações e sugestões), e para que a **equipe de
operação** faça a triagem, o atendimento e a resolução dentro de um SLA.

Este repositório é a versão em **Django** do projeto `portal-ocorrencias`
(Next.js + Supabase). As telas, as regras de negócio e os papéis são os
mesmos; o backend, o banco, a autenticação e os arquivos agora ficam todos no
Django. O de/para entre as duas versões está em
[docs/02-arquitetura.md](docs/02-arquitetura.md#de-para-com-o-projeto-original).

## Funcionalidades

- **Portal do cliente** (`/portal/`): abrir ocorrência (formulário em 2
  passos, importação de planilha, rascunho), acompanhar, conversar com a
  operação, aprovar ou reabrir, e painel de indicadores da empresa.
- **Operação** (`/operacao/`): fila com abas e busca; atendimento (status,
  prioridade, responsável, nota interna, solicitar coleta); arquivar e
  lixeira (só admin); painel com gráficos e exportação para Excel; cadastro de
  empresas, usuários (convite por e-mail), avisos, contatos de
  encaminhamento e regras de SLA.
- **Público**: página inicial e consulta de protocolo sem login
  (`/consulta`).

## Stack

| Camada | Tecnologia |
| --- | --- |
| Backend | Python 3.12+, Django 6.1 |
| Banco | SQLite em desenvolvimento, PostgreSQL do Supabase em produção |
| Hospedagem | Vercel (função Python) + Supabase Storage para anexos |
| Front-end | Templates Django, Tailwind v4, Alpine.js, Lucide, Chart.js (todos via CDN, sem etapa de build) |
| Planilhas | openpyxl (importação e exportação `.xlsx`) |
| E-mail | `django.core.mail` (SMTP; sem SMTP, as mensagens saem no console) |
| Testes | pytest + pytest-django + pytest-cov (ver [docs/05-testes.md](docs/05-testes.md)) |

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py popular_demo
.venv\Scripts\python manage.py runserver
```

Abra http://localhost:8000. O `popular_demo` cria usuários de exemplo (admin,
operador e clientes); os e-mails e a senha estão em
[popular_demo.py](ocorrencias/management/commands/popular_demo.py).

Para criar o **primeiro admin** de verdade, use
`python manage.py createsuperuser` (ele já nasce com papel `admin`). Os
demais usuários são convidados pela tela Operação → Usuários.

Testes (instale as dependências de desenvolvimento uma vez):

```bash
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest              # suíte completa
.venv\Scripts\python -m pytest -m regressao # só a regressão
.venv\Scripts\python -m pytest --cov        # com cobertura
```

Arquivamento automático das ocorrências concluídas há mais de 30 dias (agende
no cron ou no Agendador de Tarefas do Windows):

```bash
.venv\Scripts\python manage.py arquivar_concluidas --dias 30
```

## Papéis

| Papel | Acesso |
| --- | --- |
| `cliente` | Portal. Abre e acompanha as próprias ocorrências e vê, só para leitura, as dos colegas da mesma empresa. |
| `operador` | Operação. Atende, responde, muda status e gerencia empresas, usuários, avisos e contatos. |
| `admin` | Tudo do operador, mais SLA, lixeira (exclusão definitiva) e conceder o papel `admin`. |

Todo usuário convidado nasce `cliente`. Só um admin concede ou retira `admin`.

## Estrutura do projeto

```
config/              settings, urls raiz, wsgi/asgi
contas/              usuário (login por e-mail), empresa, convites e senha
ocorrencias/
  models.py          entidades do domínio; regras que eram triggers ficam no save()
  labels.py          enums, rótulos e classes de cor (fonte única de verdade)
  permissoes.py      quem vê e quem age em cada ocorrência (substitui o RLS)
  servicos.py        regras de negócio (abrir, responder, mudar status, coleta…)
  views/             camada HTTP: publico, portal, operacao, comum
  kpis.py, sla.py    cálculos puros (painel do cliente, prazos)
  emails.py, notificacoes.py, planilhas.py, uploads.py
  management/        comandos: popular_demo, arquivar_concluidas
tests/               pytest: unit, regras, http e regressao (docs/05-testes.md)
templates/           HTML (Django templates + Alpine.js)
static/              sac.css (sistema visual e tokens de cor), app.css e app.js
docs/                documentação viva (visão, arquitetura, domínio, processo)
```

As pastas `specs/` e `.claude/` e o `CHANGELOG.md` ficam só na máquina de
quem desenvolve (estão no `.gitignore`).

## Padrões adotados

### Código

- **Domínio em português.** Modelos, campos, funções e URLs usam os termos do
  negócio (`Ocorrencia`, `atribuido_a`, `solicitar_coleta`). Termos do
  framework continuam em inglês (`save`, `queryset`, `request`).
- **Camadas separadas:**
  - `views/` cuida apenas de HTTP: lê o request, chama o serviço e renderiza;
  - `servicos.py` concentra as regras e devolve um `Resultado` (`erro`,
    `aviso`, `dados` e a propriedade `ok`), sem lançar exceção para erro de
    negócio;
  - `permissoes.py` decide visibilidade e ação, e é usado tanto pelas views
    quanto pelos serviços.
- **Regras críticas no modelo.** Protocolo, SLA, histórico de status e
  notificações acontecem em `Ocorrencia.save(por=usuario)` e
  `Mensagem.save()` (notificação). Por isso, **nunca altere `status` com
  `QuerySet.update()`**: carregue a ocorrência e chame `save(por=...)`.
- **Autorização sempre no servidor.** O template esconde o botão, mas quem
  garante a regra é a view ou o serviço, com os decorators de
  [views/comum.py](ocorrencias/views/comum.py) (`cliente_required`,
  `operacao_required`, `admin_required`) e as funções de `permissoes.py`.
- **Erros visíveis.** Toda ação que falha devolve uma mensagem compreensível
  para a tela; nada falha em silêncio (ver spec 007).
- **Enums e cores em um só lugar.** Valores, rótulos e classes Tailwind de
  status, prioridade e categoria ficam em `labels.py`. Templates não
  repetem esses literais.
- **E-mail é best-effort.** A falta de SMTP ou uma falha de envio nunca
  interrompe a operação principal.
- **Entrada nunca derruba a página.** Ids e valores vindos do formulário são
  validados (`uuids_validos`); um valor adulterado gera mensagem de erro, não
  erro 500.
- **Anexos protegidos.** Os arquivos ficam em `MEDIA_ROOT` e só são baixados
  pela view `/anexos/<id>`, que confere a permissão de quem pede.

### Processo: Spec-Driven Development

Nenhuma feature, melhoria ou bug não trivial entra em desenvolvimento sem uma
spec escrita (pasta local `specs/`, fora do versionamento). O fluxo completo,
do card do Trello à spec concluída, e o modelo de spec estão em
[docs/04-processo-sdd.md](docs/04-processo-sdd.md).

### Testes

Toda feature, melhoria e correção entra com teste automatizado, e todo `bug:`
com um **teste de regressão** que falhava antes da correção. A suíte (pytest)
fica em `tests/`, dividida em `unit`, `regras`, `http` e `regressao`, e roda
na integração contínua. O padrão completo está em
[docs/05-testes.md](docs/05-testes.md).

### Commits e branches

Mensagens no formato `tipo: descrição curta no imperativo`, em português:

| Tipo | Quando usar | Exemplo |
| --- | --- | --- |
| `feat:` | Funcionalidade nova | `feat: seletor falta/sobra na troca de volume` |
| `fix:` | Ajuste ou correção pequena, sem defeito reportado | `fix: alinha foto do produto ao texto` |
| `bug:` | Correção de defeito reportado (spec do tipo Bug/GAP) | `bug: mostra o motivo do erro ao enviar mensagem` |
| `release:` | Fechamento de versão (acompanha a tag) | `release: v0.2.0` |
| `docs:` | Só documentação | `docs: explica o cálculo de SLA` |
| `refactor:` | Mudança interna sem alterar comportamento | `refactor: extrai cálculo de SLA` |
| `test:` | Só testes | `test: cobre visibilidade entre empresas` |
| `chore:` | Configuração, dependências, tarefas de manutenção | `chore: atualiza Django para 6.1.2` |

Quando existir spec, cite o número no corpo do commit (`Spec: 004`). Os
commits não levam linhas de coautoria. Os detalhes, inclusive a nomenclatura
de branches e o versionamento, estão em [CONTRIBUTING.md](CONTRIBUTING.md).

## Variáveis de ambiente

Ver [.env.example](.env.example). Sem `.env`, o projeto roda em modo de
desenvolvimento com SQLite. O e-mail é opcional: sem SMTP configurado, o
conteúdo (inclusive os links de convite) aparece no console do `runserver`.

## Produção

Hospedado na **Vercel**, com banco e anexos no **Supabase**: Postgres no schema
`django` e bucket privado no Storage. O passo a passo (Supabase, migrations,
variáveis da Vercel e roteiro de teste) está em
[docs/06-deploy.md](docs/06-deploy.md).

- As migrations rodam **manualmente**, antes do deploy, pela conexão direta.
- Com `DJANGO_DEBUG=false` a aplicação não sobe com chave fraca e liga HTTPS,
  cookies seguros e HSTS.
- Fotos são reduzidas no navegador (limite de 4,5 MB por requisição da Vercel).
- O CI também roda a suíte num Postgres com o mesmo schema e usuário da produção.
- Melhoria futura: compilar o Tailwind com `@tailwindcss/cli` em vez do script
  de navegador.

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [docs/01-visao-geral.md](docs/01-visao-geral.md) | Produto, papéis, ciclo de vida da ocorrência |
| [docs/02-arquitetura.md](docs/02-arquitetura.md) | Camadas, fluxo de uma requisição, segurança, front-end |
| [docs/03-modelo-dominio.md](docs/03-modelo-dominio.md) | Entidades, enums, relacionamentos e regras |
| [docs/04-processo-sdd.md](docs/04-processo-sdd.md) | Do card do Trello à spec, ao código e ao commit |
| [docs/05-testes.md](docs/05-testes.md) | Padrão de testes com pytest e suíte de regressão |
| [docs/06-deploy.md](docs/06-deploy.md) | Deploy na Vercel com Supabase, passo a passo |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branches, commits, versionamento e checklist de PR |
