# Contrato de fechamento do notebook experimental

## Escopo e autoridade

Este contrato registra as fronteiras do lote solicitado em 2026-09-14. O alvo é
`Marcux777/TCC`, prioritariamente `experimento-notebook/`. Neste documento, caminhos
sem esse prefixo são relativos a `experimento-notebook/`, salvo indicação de raiz.
Este lote entrega somente `docs/fechamento/CONTRATO.md` e
`docs/fechamento/STATUS.md`; não autoriza executar integralmente o plano anterior.

Snapshot da auditoria: `bd5a5e78f5898b52d58508c84f8e7b788ba0175d`.
HEAD remoto observado no início: o mesmo commit, na branch `main`.
A observação remota não comprova o estado de um checkout local.

A fonte científica é [main.tex da raiz](../../../main.tex), particularmente
`ch:metodologia`, `tab:plano-fatorial`, `tab:parametros-experimentais`,
`tab:politicas-experimento` e `sec:disponibilidade-dados-codigo`.
Consultar sob demanda apenas as seções pertinentes da
[especificação de 2026-09-02](../superpowers/specs/2026-09-02-notebook-experimental-completo-design.md)
e do [plano de 2026-09-03](../superpowers/plans/2026-09-03-notebook-experimental-completo-implementation.md).
Estes documentos orientam engenharia; não substituem o protocolo científico.

Registrar divergências em [STATUS.md](STATUS.md), com origem, impacto e disposição.
Não mudar hipóteses, limiares, parâmetros ou interpretações para acomodar código ou
resultados. Uma divergência não resolvida bloqueia a parte dependente: não permite
escolher silenciosamente a versão mais conveniente nem migrar receipts e hashes.
Não afirmar aprovação humana a partir do texto de um plano.

## Preservação do estado de trabalho

Antes de cada lote, registrar HEAD, branch, alterações staged/unstaged e arquivos
não rastreados do checkout efetivamente acessível. Comparar com o snapshot, ler o
trabalho posterior pertinente e preservá-lo. Não executar reset, clean, descarte,
rebase destrutivo, force push ou sobrescrita de alterações de terceiros.

Quando o checkout não estiver acessível, registrar a inspeção local como BLOCKED e
os comandos não executados como NOT_RUN. Nunca declarar a árvore local limpa com
base apenas no GitHub. Mudanças por API devem preservar a árvore-base e ser
publicadas sem sobrescrever refs ou trabalho concorrente; sem merge automático.

## Fronteiras científicas preservadas

| Dimensão | Invariante deste fechamento |
| --- | --- |
| Problema | Despacho online sob restrições; quatro etapas: entrada, pesagem inicial, descarga e pesagem final; pool de balanças compartilhado/reentrante. |
| Hipóteses | H1 é a hipótese comparativa; A1 e A2 são critérios de aceitação de engenharia, não novas hipóteses de superioridade. |
| H1 | Redução de pelo menos 15% na mediana pareada do p95 da espera acumulada, em média e alta congestão separadamente, com guarda de throughput `delta(N)=max(2,0.02*N)`. |
| Painel | `fifo_strict`, `fifo_flow_faithful`, `priority_local`, `fixed_score`, `lexicographic`. FIFO estrito permanece controle descritivo, fora dos três contrastes substantivos de H1. |
| Desenho | `N={60,120,180}`, `m={1,2,3}`, `b={1,2}`, quatro regimes e sementes `101..150`: 72 configurações, 3.600 instâncias e 18.000 policy-days no plano bruto. Cardinalidade planejada não comprova execução. |
| Congestão | `rho=N/min(36*m,72*b)`; baixa `<0.70`, média `[0.70,0.85)`, alta `>=0.85`; estratos independentes da política. |
| Controles | Preservar horizonte de 720 minutos, distribuições, `H0=6`, limiares tau, buffer 12, pesos do escore fixo e demais parâmetros canônicos; sem recalibração pelo piloto. |
| Pareamento | Preservar CRN e pares cenário + semente. A identidade da política não participa da chave aleatória; não reamostrar para favorecer comparadores. |
| Inferência | Não confundir validação, piloto, confirmação e sensibilidade. Manter IUT e Holm conforme main.tex; dados de desenvolvimento ou parciais não sustentam H1. |

## Interface e limites de implementação

[TCC_experimentos.ipynb](../../TCC_experimentos.ipynb) continua sendo a única
interface principal. A lógica permanece em `src/`; integrar APIs por chamadas
curtas, sem duplicar simulador, estatística ou validação em células. Não criar
outro notebook principal. Preservar Windows, caminhos portáveis, parâmetros,
sementes, comparadores e a separação das fases.

Não alterar `main.tex`, qualquer PDF, `refs.bib` ou repositórios adjacentes neste
lote. Não acrescentar RL, MILP, serviços, CI ou refatoração geral. Não importar
implementação de repositório adjacente em tempo de execução. Este contrato não
modifica notebook, `src/`, configurações, receipts ou resultados existentes.

## Estados, falhas e evidência

| Estado | Uso obrigatório |
| --- | --- |
| PASS | Aceite específico demonstrado por evidência completa e identificada; nunca sucesso global inferido de um teste parcial. |
| FAILED | Operação executada com erro, timeout ou violação de invariante. Preservar causa original, encadeamento de exceções, identificadores, logs e staging. |
| BLOCKED | Pré-requisito ausente ou incompatível antes de executar a operação dependente; registrar qual pré-requisito e sua evidência. |
| NOT_RUN | Operação não executada. Informar motivo e, quando houver, o ID do bloqueio; não atribuir resultado previsto. |

Distinguir estado da operação e diagnóstico interno: um receipt legado pode
conservar `PENDING`, mas a ação que depende da aprovação é BLOCKED. Não renomear
schemas existentes neste lote, nem converter uma falha já observada em ausência
de pré-requisito. Uma tarefa BLOCKED pode ter seu comando dependente NOT_RUN.

Sem fallback, retry, substituição por política-base, resultado anterior, zero,
NaN ou subconjunto bem-sucedido. Não usar `latest` implícito, preencher pareceres
humanos, promover dados parciais ou apagar o erro ao mudar de ferramenta. Uma
verificação posterior tem identidade e evidência próprias; não apaga a anterior.

Validação técnica reduzida deve ser explicitamente não confirmatória. A falta de
validação de face não é sanada por smoke tests. Não gerar aprovação, nomes de
revisores, datas ou hashes de fontes não efetivamente verificadas.

## Verificação, aceite e parada

Executar testes focados antes de qualquer regressão. Examinar os alvos e suas
fixtures antes de executar: pytest e o Run All padrão não podem disparar campanhas
completas. Campanhas exigem ação explícita, pré-requisitos e evidência completos.
Não executar campanha neste lote. Não apresentar números históricos como baseline
medido agora; documentar ambiente e condições de cada verificação real.

Aceite deste lote: os dois documentos existem, têm referências rastreáveis,
registram as contradições observadas e distinguem entrega documental de execução
experimental. A comparação Git deve conter somente esses dois arquivos. Nenhum
resultado científico, teste experimental ou aprovação humana é criado por isso.

Parar no aceite documental ou em impedimento real, sem avançar dependências com
base em intenção ou teste não executado. Atualizar STATUS.md após cada tarefa com
ID, estado, evidência, bloqueios e próximo aceite verificável. A entrega informa
arquivos alterados, comandos realmente executados, resultados, artefatos/hashes
e bloqueios restantes; comandos sugeridos devem ser separados dos executados.
