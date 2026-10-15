# Documentação — Portal de Ocorrências (Django)

Documentação viva do projeto. Mantenha-a atualizada no mesmo PR da mudança
que a afeta.

| Documento | Conteúdo |
| --- | --- |
| [01-visao-geral.md](01-visao-geral.md) | O que é o sistema, papéis, ciclo de vida, tipos e categorias |
| [02-arquitetura.md](02-arquitetura.md) | Camadas, fluxo de uma requisição, segurança, front-end, testes |
| [03-modelo-dominio.md](03-modelo-dominio.md) | Entidades, enums, relacionamentos e regras de negócio |
| [04-processo-sdd.md](04-processo-sdd.md) | Como um card do Trello vira spec, e a spec vira código e commit |
| [05-testes.md](05-testes.md) | Padrão de testes com pytest e suíte de regressão |
| [06-deploy.md](06-deploy.md) | Deploy na Vercel com Supabase, passo a passo |

As specs ficam na pasta local `specs/` (fora do Git), uma por card de
trabalho, a partir do `specs/TEMPLATE.md`. O processo está em
[04-processo-sdd.md](04-processo-sdd.md).

## Origem

Este material foi adaptado da documentação do projeto `portal-ocorrencias`
(Next.js + Supabase, 17/set/2026) para a implementação em Django
(15/out/2026). As referências de pesquisa que embasaram as specs 005 e 011
(painel de avisos e dashboard do cliente) continuam no repositório original,
em `docs/06-referencias-avisos-e-dashboard-cliente.md`.
