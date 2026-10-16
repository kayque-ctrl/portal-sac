# Modelo de domínio

Fonte de verdade: [contas/models.py](../contas/models.py),
[ocorrencias/models.py](../ocorrencias/models.py) e os enums em
[ocorrencias/labels.py](../ocorrencias/labels.py). Toda entidade de negócio
usa chave primária UUID.

## Entidades

| Modelo | App | Descrição |
| --- | --- | --- |
| `Usuario` | contas | Usuário (cliente, operador ou admin). Login por e-mail. `ativado_em` nulo = convite pendente |
| `Empresa` | contas | Empresa cliente; agrupa usuários do papel `cliente` |
| `Ocorrencia` | ocorrencias | Registro central: protocolo, tipo, referência, status, prioridade, responsável, SLA, arquivamento e lixeira |
| `OcorrenciaItem` | ocorrencias | Produto lançado numa ocorrência do tipo `produtos`; `sinal_volume` (falta/sobra) só na troca de volume |
| `Mensagem` | ocorrencias | Conversa cliente ↔ operação; `interna=True` é nota só da operação |
| `Anexo` | ocorrencias | Arquivo da abertura ou de uma mensagem |
| `HistoricoStatus` | ocorrencias | Auditoria de cada troca de status (consulta pública e KPIs) |
| `EventoOcorrencia` | ocorrencias | Troca de responsável e prioridade, arquivamento e lixeira, na linha do tempo (só a operação vê) |
| `Notificacao` | ocorrencias | Notificação in-app para um destinatário |
| `Aviso` | ocorrencias | Aviso do painel do portal (`info`/`alerta`), com validade opcional |
| `ContatoEncaminhamento` | ocorrencias | E-mail que recebe as novas reclamações/sugestões |
| `SlaRegra` | ocorrencias | Prazo em horas por tipo e/ou prioridade (nulo = qualquer) |
| `ProtocoloSeq` | ocorrencias | Contador do protocolo (linha única, travada com `select_for_update`) |

## Enums

```text
Papel             cliente | operador | admin
TipoPessoa        pf | pj | funcionario
OcorrenciaTipo    produtos | atraso | reclamacao_sugestao
                  | avaria | falta | sobra | troca_volume | extravio | falta_troca | outro   ← legado
ItemCategoria     avaria | falta | sobra | troca_volume | vencido | pre_vencido
SinalVolume       falta | sobra                     ← só em itens troca_volume (spec 004)
ReferenciaTipo    nf | pedido | picking             ← picking: spec 016
Status            aberta | em_analise | resolvida | concluida | recusada
Prioridade        baixa | media | alta
AvisoTipo         info | alerta
EventoTipo        responsavel | prioridade | arquivada | desarquivada | excluida | restaurada   ← spec 021
```

Rótulos que costumam confundir:

| Valor | Rótulo na tela |
| --- | --- |
| `em_analise` | Em tratativa |
| `resolvida` | Aguardando aprovação |
| `concluida` | Resolvida |

Todo card que fala em "status Em Tratativa" se refere a `em_analise`.

## Relacionamentos

```text
Empresa 1───N Usuario (papel cliente)
Usuario 1───N Ocorrencia            (cliente: quem abriu = responsável do lado do cliente)
Usuario 0..1─N Ocorrencia           (atribuido_a: responsável da operação)
Usuario 0..1─N Ocorrencia           (aprovada_por)
Ocorrencia 1───N OcorrenciaItem
Ocorrencia 1───N Mensagem 1───N Anexo
Ocorrencia 1───N Anexo              (anexos da abertura têm mensagem nula)
Ocorrencia 1───N HistoricoStatus
Ocorrencia 1───N EventoOcorrencia N───1 Usuario (autor; nulo = sistema)
Ocorrencia 1───N Notificacao N───1 Usuario (destinatario)
SlaRegra  ── tipo + prioridade ──► sla_horas / sla_prazo da Ocorrencia
```

Cuidado com a palavra "responsável": em `Ocorrencia.atribuido_a` é o
atendente da **operação**; no portal do cliente (lista e painel) é o
**autor** (`cliente`).

## Regras de negócio

### Abertura (`servicos.criar_ocorrencia`)

- Só o papel `cliente` abre ocorrência.
- Descrição com pelo menos 10 caracteres, exceto em `produtos` (os itens já
  descrevem).
- `produtos` e `atraso` exigem referência (NF, Pedido ou Picking); em
  `reclamacao_sugestao` ela é opcional. `produtos` exige ao menos um item
  (com limite de `MAX_ITENS`).
- Item com categoria em `CATEGORIAS_EXIGEM_FOTO` (`avaria`, `vencido`,
  `pre_vencido`, `troca_volume`) exige ao menos uma imagem nos anexos; o
  conteúdo da imagem é conferido (arquivo renomeado é recusado).
- `troca_volume` dispensa código, descrição e quantidade detalhada, mas
  **exige** `sinal_volume` (`falta` ou `sobra`). Sem ele, a abertura inteira é
  recusada com mensagem clara, mesmo com o formulário burlado. Nas demais
  categorias o campo é descartado. Itens antigos, sem sinal, aparecem com
  sinal neutro.
- Importação de planilha: coluna opcional `sinal` (ou o texto da categoria,
  "Troca de volume - falta"); linha de troca de volume sem sinal é ignorada e
  contada nas ignoradas.
- Anexos: até 5 arquivos de 10 MB; imagens, PDF, XLSX, XLS e CSV.
- Aviso de duplicidade (não bloqueia): se a empresa já tem ocorrência
  `aberta`, `em_analise` ou `resolvida` com a mesma referência, mostra o
  protocolo e quem abriu.
- `reclamacao_sugestao` envia e-mail para todos os `ContatoEncaminhamento`
  ativos (best-effort).

### No `Ocorrencia.save(por=...)` (antes eram triggers)

- **Protocolo** `AAAA-NNNNNN` na criação.
- **SLA na criação:** `SlaRegra.horas_para(tipo, prioridade)`; a regra mais
  específica vence, e prioridade pesa mais que tipo.
- **SLA nas trocas de status:**
  - ativo → `resolvida`: pausa e guarda o tempo restante;
  - `resolvida` → ativo: retoma do tempo restante;
  - → `concluida`/`recusada`: marca `sla_cumprido`;
  - reabertura a partir de `concluida`/`recusada`: reinicia o prazo.
- **Histórico:** registra cada troca, com `alterado_por = por`.
- **Eventos** (spec 021): troca de responsável (guarda os nomes), de
  prioridade, arquivar/desarquivar e lixeira/restaurar gravam um
  `EventoOcorrencia` com `autor = por`, comparando com os valores lidos do
  banco. O arquivamento automático grava o evento sem autor.
- **Notificações** (`notificacoes.py`): nova ocorrência vai para a
  operação; mudança de status vai para a outra parte (reabertura pelo
  cliente e conclusão avisam a operação; tratativa, aguardando aprovação e
  recusa avisam o cliente).

### Atendimento (`servicos.atualizar_ocorrencia`, `adicionar_mensagem`)

- Mudar o status exige responsável (`atribuido_a`, operador ou admin) e
  ao menos uma mensagem pública que não seja do cliente (`tem_tratativa`).
- A operação não define `concluida`; isso é aprovação do cliente.
- `recusada` exige `motivo_recusa`, que é limpo ao sair de `recusada`.
- Toda mudança de status feita pela operação envia e-mail ao cliente.
- Mensagem pública da operação numa ocorrência `aberta` muda o status para
  `em_analise`; toda resposta pública da operação envia e-mail ao cliente.
- Em `resolvida`, `concluida` e `recusada` (`STATUS_BLOQUEADOS`) a conversa
  pública fica bloqueada; nota interna continua permitida.
- Só a operação marca nota interna; o cliente nunca a vê, nem os anexos
  dela.
- "Solicitar coleta" envia e-mail à transportadora e **sempre** grava uma
  nota interna como trilha de auditoria.

### Cliente

- Só o autor aprova (`resolvida` → `concluida`, com `aprovada_por` e
  `aprovada_em`).
- Autor ou operação reabre (→ `em_analise`, desarquiva).
- Colegas da mesma empresa veem tudo menos notas internas, mas não agem.

### Linha do tempo (`apresentacao.linha_do_tempo`, spec 021)

- Uma lista só, do mais antigo ao mais novo: abertura, mensagens, trocas
  de status e, só para a operação, comentários internos e eventos.
- O cliente vê a operação como "Operação"; a operação vê o nome de quem
  escreveu.

### Ciclo de vida administrativo

- `arquivada_em`: sai da fila principal. O comando `arquivar_concluidas`
  arquiva as concluídas há mais de N dias (e grava o evento, sem autor).
- `excluida_em`: lixeira (só admin). A exclusão definitiva (`purgar`) só
  apaga o que já está na lixeira.

## Ao alterar o modelo

Toda spec que adicionar ou mudar um modelo, enum ou regra atualiza este
arquivo no mesmo PR, junto com a migration (`makemigrations`) e os testes.
