# Visão geral do produto

## O que é

O **Portal de Ocorrências** permite que clientes de uma empresa registrem e
acompanhem problemas relacionados a pedidos e notas fiscais (avarias,
faltas, sobras, trocas de volume, produtos vencidos, atrasos na entrega,
reclamações e sugestões), e que a equipe de operação faça a triagem, o
tratamento e a resolução dentro de um SLA.

Nesta operação, **o "cliente" é uma empresa**: vários usuários abrem
ocorrências em nome dela, todos acompanham todas, e quem abriu é o
responsável pela ocorrência.

Áreas:

- **Portal do cliente** (`/portal/`): abrir ocorrência, acompanhar, conversar
  com a operação, aprovar ou reabrir quando resolvida, painel de indicadores.
- **Operação** (`/operacao/`): fila, atendimento, SLA, empresas, usuários,
  avisos, contatos de encaminhamento, painel de indicadores.
- **Público** (`/`, `/consulta`): página inicial e consulta de protocolo
  sem login.

## Papéis (`contas.Usuario.papel`)

| Ação | cliente | operador | admin |
| --- | :-: | :-: | :-: |
| Abrir ocorrência | ✔ | | |
| Ver as próprias ocorrências | ✔ | ✔ | ✔ |
| Ver ocorrências de colegas da mesma empresa (leitura) | ✔ | ✔ | ✔ |
| Responder, anexar, reabrir | só quem abriu | ✔ | ✔ |
| Aprovar a resolução | só quem abriu | | |
| Ver notas internas | | ✔ | ✔ |
| Mudar status, prioridade, responsável | | ✔ | ✔ |
| Arquivar e desarquivar | | ✔ | ✔ |
| Empresas, usuários, avisos, contatos | | ✔ | ✔ |
| Regras de SLA | | | ✔ |
| Lixeira: mover, restaurar e excluir definitivamente | | | ✔ |
| Conceder ou retirar o papel `admin` | | | ✔ |

Todo usuário convidado nasce `cliente`; a promoção é feita por um admin na
tela de usuários. O primeiro admin é criado com `createsuperuser`. Uma
granularidade maior de permissões está em discussão na
spec 008.

## Ciclo de vida de uma ocorrência

```
aberta ──► em_analise ("Em tratativa") ──► resolvida ("Aguardando aprovação")
  │              ▲                            ├──► concluida  (cliente aprova; rótulo "Resolvida")
  │              └────────────────────────────┴─── reabrir    (cliente ou operação)
  └──────────────────────────────────────────► recusada      (operação, com motivo)
```

Os rótulos exibidos ficam em `Status` ([labels.py](../ocorrencias/labels.py)):
o valor `resolvida` aparece como "Aguardando aprovação" e `concluida` como
"Resolvida".

Regras principais (detalhes em [03-modelo-dominio.md](03-modelo-dominio.md)):

- A operação só muda o status depois de ter um **responsável**
  (`atribuido_a`) e pelo menos **uma resposta pública** ao cliente.
- A primeira resposta pública da operação a uma ocorrência `aberta` a move
  para `em_analise`.
- Só **quem abriu** aprova uma ocorrência `resolvida` (vira `concluida`). A
  operação não conclui no lugar do cliente.
- Reabrir (pelo autor ou pela operação) leva a ocorrência de volta para
  `em_analise` e a desarquiva.
- Recusar exige motivo.
- O SLA é definido por regra (tipo + prioridade) e **pausa** enquanto a
  ocorrência aguarda a aprovação do cliente.
- Em `resolvida`, `concluida` e `recusada` a conversa fica bloqueada; só
  reabrindo volta a aceitar mensagens.

## Tipo da ocorrência × categoria do item

São dois níveis de classificação que é preciso manter separados ao escrever
specs:

- **`OcorrenciaTipo`**, o que o cliente escolhe ao abrir. O formulário só
  oferece `produtos`, `atraso` e `reclamacao_sugestao` (`TIPOS_FORM` em
  [labels.py](../ocorrencias/labels.py)). Os demais valores (`avaria`,
  `falta`, `sobra`, `troca_volume`, `extravio`, `falta_troca`, `outro`)
  são **legado**: existem para dados antigos.
- **`ItemCategoria`**, a categoria de cada produto lançado numa ocorrência
  do tipo `produtos`: `avaria`, `falta`, `sobra`, `troca_volume`,
  `vencido`, `pre_vencido`.

Regras por categoria:

- `avaria`, `vencido`, `pre_vencido` e `troca_volume` exigem ao menos uma
  foto nos anexos (`CATEGORIAS_EXIGEM_FOTO`).
- `troca_volume` dispensa código, descrição e quantidade detalhada
  (`CATEGORIAS_DISPENSAM_DADOS_PRODUTO`).
- `troca_volume` exige informar se o volume **falta ou sobra** (spec 004);
  o item mostra "Troca de volume (falta)" e o sinal correspondente.
- `falta` e `sobra` têm sinal (− / +) na exibição (`sinal_item`).
- `avaria`, `pre_vencido` e `vencido` têm cor de fonte própria na descrição
  do produto (`ITEM_TEXTO`, spec 006).

## Ligação com o Trello

O board **Sistema de Ocorrências** é a fonte de demanda:

```
A fazer → Em andamento → A validar → Concluído
```

Cada card relevante ganha uma spec em `specs/` (pasta local) antes de
entrar em desenvolvimento. Ver [04-processo-sdd.md](04-processo-sdd.md).
