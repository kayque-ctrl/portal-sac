# Processo: Spec-Driven Development (SDD)

**Nenhuma feature, melhoria ou bug não trivial entra em desenvolvimento sem
uma spec escrita e revisada.** A spec é o contrato entre o que o card do
Trello pediu e o que o código vai fazer.

## Fluxo

```
Card no Trello ("A fazer")
   │
   ▼
1. Spec em specs/ (local) a partir do TEMPLATE.md
   contexto, objetivo, critérios de aceite,
   design técnico, perguntas em aberto
   │
   ▼
2. Resolver as perguntas em aberto críticas com quem pediu
   (ou registrar a decisão assumida, se dá para seguir sem bloquear)
   │
   ▼
3. Card → "Em andamento"; spec → "Em andamento"
   branch feature/NNN-slug | fix/NNN-slug | bug/NNN-slug
   │
   ▼
4. Implementar seguindo o plano da spec              commits feat: / fix: / bug: …
   teste junto com o código; marcar [x] no plano       (corpo: "Spec: NNN")
   bug: leva teste em tests/regressao (docs/05)
   │
   ▼
5. PR para main; card → "A validar"; spec → "Em validação"
   │
   ▼
6. Validado: card → "Concluído"; spec → "Concluída"
   na próxima versão                                 commit  release: vX.Y.Z + tag
```

## Tipo de spec → tipo de commit e branch

| Tipo na spec | Branch | Commit |
| --- | --- | --- |
| Feature | `feature/NNN-slug` | `feat:` |
| Melhoria | `fix/NNN-slug` (ajuste pequeno) ou `feature/NNN-slug` (mudança de comportamento) | `fix:` ou `feat:` |
| Bug / GAP | `bug/NNN-slug` | `bug:` |
| Documentação (`docs/`, README) | direto em `main` ou `docs/NNN-slug` | `docs:` |

Detalhes de formato em [CONTRIBUTING.md](../CONTRIBUTING.md).

## Convenções

- **Fora do Git:** a pasta `specs/` está no `.gitignore`. As specs são o
  material de trabalho de quem desenvolve; o que vai para o repositório é o
  código, os testes e a documentação em `docs/`.
- **Local:** `specs/NNN-slug-curto.md`, numeração sequencial que nunca é
  reaproveitada. Os números 001–012 são os mesmos do projeto original, para
  manter a rastreabilidade com o Trello.
- **Template:** toda spec nova parte de
  `specs/TEMPLATE.md`.
- **Rastreabilidade:** toda spec cita o(s) card(s) do Trello que a
  originaram. Quando dois cards pedem o mesmo trabalho (caso da spec 010),
  uma única spec cobre os dois e diz isso explicitamente.
- **Status:** `Backlog`, `Em andamento`, `Em validação`, `Concluída`,
  `Bloqueada`. Use `Bloqueada` quando uma pergunta em aberto impede começar,
  e diga o que falta decidir e quem decide.
- **Escopo pequeno:** uma spec deve caber num ciclo curto de
  implementação e validação. Card grande vira mais de uma spec.
- **Pergunta em aberto não bloqueia automaticamente:** se há uma decisão
  razoável, registre-a como "decisão assumida, confirmar antes do merge" e
  siga.
- **A spec acompanha o código:** se a implementação revelar algo novo,
  ajuste a spec no mesmo PR.
- **Critério de aceite testável:** cada critério vira um teste automatizado
  (padrão em [05-testes.md](05-testes.md)) e a spec cita o teste pelo id do
  pytest, ex.: `tests/regras/test_sla.py::test_sla_pausa_ao_aguardar_aprovacao`.
  Spec de bug cita o teste de `tests/regressao/`.

## Quando não escrever spec

Correções triviais e sem ambiguidade (erro de digitação, ajuste de espaçamento
sem regra de negócio) podem ir direto num commit `fix:` com descrição clara.
Na dúvida, escreva a spec: é mais barato que retrabalho.
