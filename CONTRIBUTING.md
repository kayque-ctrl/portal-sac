# Como contribuir

## Fluxo de trabalho

1. Toda mudança não trivial começa por uma spec na pasta local `specs/`,
   que não é versionada (ver [docs/04-processo-sdd.md](docs/04-processo-sdd.md)).
2. Crie uma branch a partir de `main` seguindo a nomenclatura abaixo.
3. Implemente seguindo o "Plano de implementação" da spec e marque os passos
   concluídos nela.
4. Escreva os testes junto com o código (padrão em
   [docs/05-testes.md](docs/05-testes.md)) e rode `pytest` e
   `python manage.py makemigrations --check` antes de abrir o PR.
5. Abra o PR para `main` citando a spec. O merge só acontece com os testes
   passando.

## Branches

| Prefixo | Uso | Exemplo |
| --- | --- | --- |
| `feature/` | Funcionalidade nova | `feature/004-troca-volume-falta-sobra` |
| `fix/` | Ajuste ou correção pequena | `fix/002-alinhamento-foto` |
| `bug/` | Correção de defeito reportado | `bug/007-erro-sem-motivo` |
| `release/` | Preparação de versão | `release/v0.2.0` |

Quando houver spec, o número dela vem logo depois do prefixo.

## Mensagens de commit

Formato:

```
tipo: descrição curta no imperativo (até ~72 caracteres)

Corpo opcional explicando o porquê, não o como.

Spec: 004
```

| Tipo | Quando usar |
| --- | --- |
| `feat:` | Funcionalidade nova para o usuário |
| `fix:` | Ajuste ou correção pequena, sem defeito reportado |
| `bug:` | Correção de defeito reportado (spec do tipo Bug ou GAP) |
| `release:` | Fechamento de versão, acompanhado da tag |
| `docs:` | Só documentação |
| `refactor:` | Mudança interna sem alterar comportamento |
| `test:` | Só testes (novos ou reorganizados) |
| `chore:` | Configuração, dependências, manutenção |

Regras:

- Em português, no imperativo: "adiciona", "corrige", "remove".
- Um assunto por commit. Migration e código que depende dela vão juntos.
- Código e o teste dele vão no mesmo commit. Um `bug:` leva o teste de regressão junto.
- Sem linhas `Co-Authored-By` ou outras de atribuição automática.

## Versionamento e releases

Versionamento semântico (`MAJOR.MINOR.PATCH`):

- `MAJOR`: mudança incompatível (ex.: migration que exige ação manual).
- `MINOR`: nova funcionalidade (`feat:`).
- `PATCH`: só correções (`fix:` / `bug:`).

Para fechar uma versão:

1. Faça o commit `release: vX.Y.Z` (vazio, se não houver arquivo a
   alterar: `git commit --allow-empty -m "release: vX.Y.Z"`), com o resumo
   da versão no corpo.
2. Crie a tag anotada: `git tag -a vX.Y.Z -m "vX.Y.Z"`.

O histórico de versões detalhado fica no `CHANGELOG.md` local (fora do
versionamento); a referência pública são as tags e os commits.

## Checklist do PR

- [ ] Spec criada ou atualizada (status e plano de implementação)
- [ ] `pytest` verde; `pytest --cov` acima do piso
- [ ] Teste novo na camada certa; `bug:` com teste em `tests/regressao/` que falhava antes
- [ ] Nenhum teste de regressão removido ou enfraquecido
- [ ] Sem migration pendente (`python manage.py makemigrations --check`)
- [ ] `docs/03-modelo-dominio.md` atualizado se mudou modelo, enum ou regra
- [ ] Testado no navegador em tema claro, tema escuro e celular, quando há mudança de tela
