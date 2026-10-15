# Padrão de testes

Toda feature, melhoria e correção entra com teste automatizado. A suíte roda
com **pytest** (+ `pytest-django` e `pytest-cov`) e é o que protege o sistema
contra regressões: ela precisa estar verde antes de qualquer merge.

```bash
pip install -r requirements-dev.txt

pytest                      # tudo
pytest -m regressao         # só a suíte de regressão
pytest -m "unit or regras"  # camadas rápidas
pytest tests/regras/test_sla.py::test_sla_pausa_ao_aguardar_aprovacao
pytest --cov                # com cobertura (falha abaixo do piso de .coveragerc)
```

## Estrutura

```
tests/
  conftest.py     fixtures (elenco de usuários, abrir, responder, entrar…) e marcadores
  builders.py     funções puras que montam dados de entrada (dados_atraso, foto…)
  unit/           lógica pura, sem banco nem HTTP
  regras/         serviços, modelos e permissões, com banco
  http/           telas e fluxos pelo client HTTP do Django
  regressao/      bugs corrigidos e regras críticas (segurança, acesso, erros)
```

O marcador de cada teste é aplicado **pela pasta** (`tests/unit` → `unit`,
`tests/regressao` → `regressao`…); não é preciso decorá-lo.

| Camada | Testa | Banco | Velocidade |
| --- | --- | :-: | --- |
| `unit` | funções puras (`kpis.py`, `formato.py`, `labels.py`) | não | ms |
| `regras` | `servicos.py`, `save()` dos modelos, `permissoes.py`, `sla.py` | sim | rápida |
| `http` | views, templates, redirecionamentos, formulários | sim | média |
| `regressao` | o que **nunca** pode voltar a quebrar | sim | média |

## Onde colocar o teste novo

1. Regra de negócio nova ou alterada → `tests/regras/` (chame o serviço direto).
2. Tela, formulário ou rota nova → `tests/http/` (um teste de renderização e um
   do fluxo principal).
3. Cálculo puro → `tests/unit/`.
4. **Bug corrigido ou regra de segurança** → `tests/regressao/` (ver abaixo).

Um teste novo de feature normalmente vai em duas camadas: a regra em `regras/`
e o caminho feliz pela tela em `http/`.

## Convenções

- **Nome** em português descrevendo o comportamento, não a função:
  `test_colega_nao_envia_mensagem`, não `test_adicionar_mensagem_2`.
- **Arrange / Act / Assert**, separados por linha em branco. Um comportamento
  por teste; vários `assert` só quando descrevem o mesmo resultado.
- **Fixtures, não herança.** Os usuários vêm de `conftest.py`:

  | Fixture | O que é |
  | --- | --- |
  | `cliente`, `colega` | dois usuários da empresa ACME (`colega` só lê) |
  | `estranho` | usuário de outra empresa (Globex) |
  | `sem_empresa` | cliente sem empresa |
  | `operador`, `admin` | operação e administrador |
  | `abrir(**extra)` | abre uma ocorrência de atraso (como `cliente`) |
  | `responder(oc)` | a operação responde (aberta → em tratativa) |
  | `ocorrencia` | avaria da `cliente`, com foto e resposta com anexo |
  | `entrar(user)` | `client.force_login(user)` e devolve o client |

  Peça só as fixtures que o teste usa; criar usuário a mais deixa o teste
  lento e confuso.
- **Dados de entrada em `builders.py`.** `dados_atraso()`, `dados_produtos("avaria")`,
  `foto()`. Passe só o que muda: `dados_atraso(descricao="curta")`.
- **Variações em `parametrize`**, não em `for` com `subTest`:
  ```python
  @pytest.mark.parametrize(("extra", "erro"), [({"tipo": "outro"}, "Selecione um tipo válido.")])
  ```
- **Mensagens de erro exatas.** Compare o texto que o usuário vê: se ele mudar,
  é uma mudança de comportamento que deve ser consciente.
- **Entrada adulterada.** Todo id, número ou data que vem de formulário ou
  querystring ganha um teste com valor malformado (`"lixo"`, vazio, negativo).
  O esperado é mensagem de erro ou valor ignorado, **nunca erro 500**. Ver
  `tests/regressao/test_ids_malformados.py`.
- **Sem rede, sem relógio, sem disco real.** E-mail vai para `mail.outbox`
  (`mailoutbox`), anexos para uma pasta temporária (fixture automática),
  integrações externas com `mock.patch`. Para tempo, mude o dado
  (`Ocorrencia.objects.filter(...).update(sla_prazo=...)`) em vez de dormir.
- **Nunca altere `status` com `update()` para montar um cenário** que depende de
  SLA, histórico ou notificação: use `oc.status = ...; oc.save(por=usuario)`.
  `update()` é aceitável para forjar datas, como acima.
- **Warnings de depreciação falham o teste** (`pytest.ini`). Corrija a causa;
  não adicione `ignore`.

## Testes de regressão

A pasta `tests/regressao/` é o **contrato do que já funcionou e não pode
quebrar**. Regras:

1. **Todo `bug:` entra com um teste de regressão** em `tests/regressao/`, que
   deve **falhar antes da correção** e passar depois. Faça o teste primeiro,
   veja-o falhar, depois corrija.
2. O docstring do módulo começa com `Protege: spec NNN (assunto).` ou
   `Protege: bug NNN (assunto).`, ligando o teste à spec.
3. Nome do arquivo pelo assunto (`test_visibilidade_empresa.py`), não pelo
   número do bug.
4. **Nunca apague nem enfraqueça** um teste de regressão para fazer a suíte
   passar. Se a regra mudou de verdade, altere o teste **na mesma mudança da
   spec** e diga isso no commit.
5. Regras de segurança (quem vê, quem age, escalada de papel) vivem aqui, mesmo
   sem bug histórico: a falha delas é o pior tipo de regressão.
6. Para um bug conhecido ainda não corrigido, escreva o teste com
   `@pytest.mark.xfail(strict=True, reason="bug NNN")`: ele documenta o defeito
   e **avisa quando for corrigido** (o `strict` o faz falhar ao passar, e
   você remove o `xfail`).

### Matriz de acesso

`tests/regressao/test_acesso_por_papel.py` cruza **6 papéis × 12 rotas**. Rota
nova ⇒ linha nova em `ROTAS`. Se uma célula mudar, é uma mudança de permissão
e precisa estar na spec (ver spec 008).

## O que testar em cada tipo de mudança

| Mudança | Mínimo exigido |
| --- | --- |
| `feat:` regra nova | teste em `regras/` do caminho feliz e de cada erro novo; tela em `http/` |
| `feat:` tela nova | renderização para cada papel permitido; linha na matriz de acesso |
| `fix:` ajuste | teste que cobre o ajuste, se houver comportamento; só visual: nada além da checagem manual |
| `bug:` defeito | teste em `regressao/` que falha antes da correção |
| mudança de modelo | migration + `makemigrations --check` limpo + teste da regra |
| mudança de permissão | atualizar a matriz de acesso e a spec |
| `refactor:` | nenhum teste novo; a suíte existente deve passar **sem alteração** |

## Cobertura

`pytest --cov` falha abaixo do piso de `.coveragerc`: hoje **99%**, com
cobertura real de 99,95% (567 testes). O piso só sobe. Código novo entra
coberto. Se uma linha for de fato inalcançável (código defensivo), explique por
que no PR em vez de baixar o piso.

A única linha descoberta é defensiva: `planilhas._ler_xlsx` quando o arquivo
não tem planilha, algo que o openpyxl não produz.

Cobertura alta não é o objetivo; é consequência. Um teste que só "passa por"
uma linha sem verificar o resultado não conta. Todo teste afirma um
comportamento observável (retorno, mensagem na tela, linha no banco, e-mail
enviado).

## Integração contínua

`.github/workflows/testes.yml` roda, em todo push para `main` e em todo PR:

1. `makemigrations --check --dry-run` (modelo e migrations em dia);
2. `pytest --cov` (suíte completa, incluindo a regressão).

PR com a suíte vermelha não é mesclado.

## Checklist antes do commit

- [ ] `pytest` verde, sem warnings novos
- [ ] Teste novo na camada certa; `bug:` com teste em `regressao/`
- [ ] `pytest --cov` acima do piso
- [ ] Nenhum teste de regressão removido ou enfraquecido
