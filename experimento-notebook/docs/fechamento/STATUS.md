# Estado compacto do fechamento

Atualizado em 2026-09-14. Escopo: lote documental; não é fechamento experimental.
Contrato vigente: [CONTRATO.md](CONTRATO.md). Caminhos abaixo são relativos a
`experimento-notebook/`, salvo indicação de raiz.

## Estado verificado

- Repositório: `Marcux777/TCC`; branch-base: `main`.
- Snapshot da auditoria e HEAD remoto inicial: `bd5a5e78f5898b52d58508c84f8e7b788ba0175d`.
- Árvore-base Git: `9e71f62db3952c6b9af3d3a9005d3500ca042686`.
- `docs/` continha somente `superpowers/` nessa árvore; os dois documentos de fechamento são adições.
- Nenhum checkout preexistente foi encontrado nos diretórios de trabalho inspecionados. O computador do usuário não foi inspecionado; não se afirma árvore local limpa.
- O commit-base declara Task 3/proveniência WIP: callers do loader e validação recursiva incompletos; relata falha do teste header-only após troca de `expected_plan` por root pin obrigatório. Isso é evidência histórica, não teste reproduzido neste lote.

## Tarefas e verificações

| ID | Estado | Evidência / limite / próximo aceite |
| --- | --- | --- |
| F00-HEAD | PASS | HEAD e árvore remotos lidos pelo conector GitHub, com SHA fixado acima. |
| F01-CONTRATO | PASS | Fronteiras, autoridade científica, estados e aceite documentados; verificação documental V01-DOCS. Não implica enforcement no runtime. |
| F02-STATUS | PASS | Estado, fontes, contradições e bloqueios registrados; verificação documental V01-DOCS. Não declara conclusão da Task 3. |
| V01-DOCS | PASS | 8 checagens estruturais locais dos dois Markdown: escopo, formato, referências, hashes Git citados e consistência dos estados. Não equivalem a pytest do projeto. |
| E01-CLONE | FAILED | `git clone` terminou com exit 128: `Could not resolve host: github.com`. Sem retry. |
| E02-LOCAL | BLOCKED | Checkout real e alterações locais indisponíveis; `git status` e `git rev-parse HEAD` do projeto: NOT_RUN. |
| T03-PROVENIENCIA | NOT_RUN | Retomada da Task 3 fora deste lote. Próximo aceite: reproduzir a falha focada, preservar sua causa e validar callers/proveniência sem campanha. |
| G01-FACE | BLOCKED | Receipt versionado está `PENDING`, sem IDs de revisores e sem hashes preenchidos; não comprova aprovação humana. Ver C01/C02. |
| V02-REGRESSAO | NOT_RUN | Sem checkout executável (E02-LOCAL); nenhuma regressão, compileall do projeto ou teste Windows executado. |
| V03-NOTEBOOK | NOT_RUN | Notebook não executado nem alterado. Run All e campanha completa não executados. |
| G02-CAMPANHAS | BLOCKED | G01-FACE impede as fases dependentes; geração principal, piloto, confirmação e sensibilidade: NOT_RUN. Não houve inspeção de dataset externo nem gate de capacidade. |

## Contradições e disposição

| ID | Fontes e diferença observada | Disposição neste lote |
| --- | --- | --- |
| C01-FONTE | `main.tex` da raiz, `sec:disponibilidade-dados-codigo`, declara fonte canônica do protocolo; a especificação de 2026-09-02, abertura e barreira de face, prioriza `main.pdf` e seus hashes. O pedido atual fixa `main.tex`. | Prevalece `main.tex` como autoridade científica deste fechamento. Não editar PDF, especificação, código ou receipt, nem trocar hashes silenciosamente. Compatibilização do vínculo de proveniência: NOT_RUN; não promover pacote incompatível. |
| C02-FACE | `main.tex`, metodologia antes de `sec:input-modeling`, prevê validação ainda futura com orientadora e especialista quando disponível. A especificação, barreira de face, exige rodada cega com pelo menos dois revisores independentes. | Registrar diferença de critério, sem inventar revisão nem dispensar a barreira. Receipt real permanece PENDING e fases dependentes BLOCKED. Alinhar critério verificável à fonte canônica em lote próprio antes de promoção. |
| C03-ESTADOS | Especificação/plano usam diagnósticos `PENDING`, `INVALID_INPUT` e `NOT_RUN_NO_FROZEN_DATASET`; o pedido atual exige distinguir FAILED, BLOCKED e NOT_RUN. | Usar os estados operacionais deste contrato e conservar diagnóstico/causa legado como evidência. Nenhuma migração de schema ou mudança de comportamento foi implementada. |

Seções consultadas do design: abertura, objetivo/fronteira científica, barreira de
face e protocolo congelado pertinente. Do plano: objetivo/arquitetura, Global
Constraints e interfaces pertinentes. Não se executou o plano integral nem se
assumiu aprovação humana a partir de seus títulos/checklists. O critério de face
acima descreve a divergência nos trechos consultados, não uma revisão exaustiva.

## Identidade das fontes

Os identificadores abaixo são **Git blob SHA-1**, não SHA-256 de arquivos lidos
integralmente no ambiente local. Todos pertencem ao commit-base fixado acima.

| Fonte | Git blob SHA-1 |
| --- | --- |
| `main.tex` (raiz) | `475f7b5a60f6e0d02ceeab93bb8aec233ec64dc0` |
| `docs/superpowers/specs/2026-09-02-notebook-experimental-completo-design.md` | `520e254faae50641bcb8aa6b63f873e3901ed463` |
| `docs/superpowers/plans/2026-09-03-notebook-experimental-completo-implementation.md` | `42111ec894947395578600cc15637d3db5aa40d2` |
| `TCC_experimentos.ipynb` (identidade; não executado) | `6dff569c50a8271b81f50a3108a7f4b341f83f48` |
| `inputs/face_validation_receipt.json` | `7a0b863f3dfd53741efed8178ca389129feb414a` |

## Execução deste lote

O acesso remoto usa o conector GitHub, já disponível antes da tentativa de clone.
Leituras remotas e verificações dos documentos são operações distintas; não
substituem checkout, execução experimental ou a falha E01-CLONE por PASS.

Comando de clone efetivamente executado:

```text
git clone --no-tags https://github.com/Marcux777/TCC.git /mnt/data/TCC
```

Causa preservada (exit 128):

```text
fatal: unable to access 'https://github.com/Marcux777/TCC.git/': Could not resolve host: github.com
```

Verificação documental efetivamente executada sobre o pacote de entrega, não
sobre um checkout do projeto:

```text
python -m unittest discover -s /mnt/data/tcc-fechamento-evidence -p test_fechamento_docs.py -v
```

Resultado: 8 testes, OK, exit 0. O script e seus logs integram o pacote de evidências
da entrega, fora do repositório; não são apresentados como suíte experimental.

Baseline de testes do projeto neste lote: NOT_RUN. O resultado `162 passed,
1 warning, 1085.09 s` mencionado no plano é histórico, não resultado desta entrega.
Nenhum arquivo de `src/`, configuração, notebook, receipt, resultado, manuscrito,
PDF ou bibliografia é modificado por este lote.

## Próxima retomada

Em checkout real, registrar HEAD/branch/staged/unstaged/untracked sem descartar
trabalho posterior; ler C01/C02 antes de tocar proveniência. Executar apenas o
reprodutor focado da Task 3 e seus testes pertinentes. Não abrir regressão antes
de inspecionar fixtures e comprovar que não disparam campanhas. Não avançar piloto
ou confirmação enquanto seus pré-requisitos não tiverem evidência completa.
