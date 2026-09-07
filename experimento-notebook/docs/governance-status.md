# Governança e estado das entregas

Estado documental em 7 de setembro de 2026. O protocolo científico continua em
[main.tex](../../main.tex); este registro distingue evidência disponível de
aprovação ou entrega pendente. Testes e fixtures não são resultados da campanha principal.

| Evidência ou entrega | Estado | O que ela permite concluir |
| --- | --- | --- |
| Validação humana de face dos parâmetros, cenários e rastros exemplares | **PENDING** no [recibo real](../inputs/face_validation_receipt.json) | Ainda não há aprovação externa dos parâmetros. A [rubrica](../inputs/face_validation_rubric.v1.json) exige dois revisores independentes, critérios atendidos ou divergências resolvidas e documentadas; recibo, documento e configuração precisam corresponder. |
| Ensaio do operador no DES | **Sintético, aceitação automática** | A cadeia recomendação → aceitação → serviço é exercitada. Não demonstra participação humana nem escolha autônoma de um operador. |
| Auditoria estrutural automatizada de A2 | **Implementada, resultado por execução** | Confere campos, causas, contexto, FIFO, observações dos eventos, replay e proveniência. Sucesso estrutural não mede legibilidade para pessoas nem aprova A2 em seu escopo humano. |
| Revisão humana da amostra A2 | **PENDING** | Faltam seleção e inspeção reais da amostra, pareceres e, quando aplicável, concordância entre avaliadores. A aprovação de face não substitui essa revisão. |
| Cena, importador e replay em Unreal Engine 5.8 | **NÃO ENTREGUE / PENDENTE** | O objetivo tridimensional permanece no escopo. A inicialização de projeto e o replay Python não entregam essa demonstração. |
| Campanha principal e conclusão de H1 | **Resultados indisponíveis** | Execuções de engenharia, fixtures e saídas auxiliares RHFS não compõem as 18.000 execuções confirmatórias nem demonstram superioridade do motor. |

## Semântica do operador e cobertura existente

O modo corrente é `operator_mode="synthetic_auto_accept"`. O evento
`OPERATOR_DECISION` transporta `decision="accept"`; no envelope de log, o campo
correspondente é `operator_decision`. O nome do evento não identifica uma pessoa.
O manifesto mantém `human_audit_status="pending"` e
`global_acceptance_status="pending"`. O caminho automático não aceita promover a
revisão humana a `complete` sem um processo humano verificável, ainda não implementado.

A inspeção dos testes existentes distingue dois comportamentos:

- [test_every_selection_is_explained_then_accepted_before_service](../tests/test_dispatch_emulator.py)
  verifica a cadeia de aceitação automática antes do serviço.
- [test_replay_requires_matching_accepted_decision_before_service](../tests/test_digital_model_replay.py)
  introduz `decision="reject"` e espera erro. Isso verifica falha segura para um
  evento não suportado; não implementa rejeição operacional seguida de nova decisão.

Não há demonstração concluída de rejeição pelo operador, substituição por outro
candidato admissível ou participação humana no DES. A regra `fifo_override`
descreve uma quebra de FIFO causada pela política; não é uma sobreposição humana.
Fixtures com nomes de pessoas ou recibos `APPROVED` existem para testar limites do
software e nunca devem ser promovidas a avaliações reais.

## O que falta para as alegações pendentes

A rodada real de face deve produzir o recibo e as evidências previstos na rubrica.
A avaliação humana de A2 deve produzir sua própria amostra, julgamentos e trilha
de revisão. O fluxo de intervenção autorizada deve ser implementado e demonstrado
com rejeição e substituição admissível, preservando as restrições rígidas e o motivo
registrado. A demonstração Unreal requer cena, ativos, importador e controles de
replay executáveis. A campanha principal depende dos pré-requisitos científicos e
de capacidade, seguida da execução, auditoria e análise de H1.

A evidência auxiliar de poder RHFS cobre um único Wilcoxon sobre contrastes
reamostrados. Ela não estima a potência da decisão completa de H1, que também exige
três comparadores, a guarda de throughput, o limiar de 15% e Holm entre estratos.
Os números arquivados não devem ser apresentados como resultados da campanha principal.
