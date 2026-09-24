# Governança e estado das entregas

## Protocolo vigente: 2.0.0 (24 de setembro de 2026)

A [emenda prospectiva](protocol-v2-amendment.md) reformula a avaliação como
estudo computacional sintético. Parâmetros são hipóteses de engenharia;
face e revisão por pessoas são `NOT_EVALUATED` e não impedem campanhas v2.
A2 exige rastreabilidade e reconstruibilidade automatizadas. Não se alega
validação humana, legibilidade ou validade operacional externa.

O recibo v1 permanece `PENDING`. Novos artefatos identificam v2 e seu hash,
mantendo A1, CRN, capacidade, integridade e critérios de H1. Piloto, principal,
estresse, painel exploratório, Unreal e redação continuam necessários.
O notebook central reúne a execução e seu estado efetivo.

### Execução integral tentada em 24/09/2026

O notebook foi iniciado com o plano integral e interrompido antes da geração
por insuficiência de armazenamento: mínimo principal de 93.842.309.120 bytes,
ainda sem dataset, contra 37.021.134.848 bytes livres no momento da tentativa.
O registro original é `results/20260924T100138Z-99c6f704/storage.json`; a exceção
está nas saídas do notebook. Nenhuma campanha científica foi concluída.

A [consulta técnica em ChatGPT 6 Pro](https://chatgpt.com/c/6ab4f23b-4f58-83e9-8eab-dee4911731a4),
uma consulta enviada e respondida, confirmou a consequência aritmética do gate:
compressão ou execução em lotes não suprem capacidade livre exigida pela
fórmula vigente. A recomendação foi confrontada com `capacity.py` e adotada
somente para preservar o bloqueio, sem apagar dados ou mudar o protocolo.

O notebook agora orquestra todas as fases e as políticas exploratórias têm
implementação. Verificações de software não equivalem à campanha integral;
execução científica, cena/replay Unreal e integração dos resultados no texto
continuam pendentes. Face e revisão humana não são pendências obrigatórias v2.

## Registro histórico do protocolo 1.0.0

O registro abaixo documenta requisitos anteriores, substituídos somente nos
pontos humanos indicados na emenda v2. Não autoriza preencher aprovações ou
reinterpretar resultados antigos.

Estado documental em 7 de setembro de 2026. O protocolo científico continua em
[main.tex](../../main.tex); este registro distingue evidência disponível de
aprovação ou entrega pendente. Testes e fixtures não são resultados da campanha principal.

| Evidência ou entrega | Estado | O que ela permite concluir |
| --- | --- | --- |
| Validação humana de face dos parâmetros, cenários e rastros exemplares | **PENDING** no [recibo real](../inputs/face_validation_receipt.json) | Ainda não há aprovação externa dos parâmetros. A [rubrica](../inputs/face_validation_rubric.v1.json) exige dois revisores independentes, critérios atendidos ou divergências resolvidas e documentadas; recibo, documento e configuração precisam corresponder. |
| Ensaio do operador no DES | **Sintético: aceitar, rejeitar e override admissível** | Ensaios separados exercitam as três respostas com origem simulada, motivo e replay de JSONL persistido. A matriz científica conserva aceitação automática. Não há participação humana demonstrada. |
| Auditoria estrutural automatizada de A2 | **Implementada, resultado por execução** | Confere campos, causas, contexto, FIFO, observações dos eventos, replay e proveniência. Sucesso estrutural não mede legibilidade para pessoas nem aprova A2 em seu escopo humano. |
| Revisão humana da amostra A2 | **PENDING** | Faltam seleção e inspeção reais da amostra, pareceres e, quando aplicável, concordância entre avaliadores. A aprovação de face não substitui essa revisão. |
| Cena, importador e replay em Unreal Engine 5.8 | **NÃO ENTREGUE / PENDENTE** | O objetivo tridimensional permanece no escopo. A inicialização de projeto e o replay Python não entregam essa demonstração. |
| Campanha principal e conclusão de H1 | **Resultados indisponíveis** | Execuções de engenharia, fixtures e saídas auxiliares RHFS não compõem as 18.000 execuções confirmatórias nem demonstram superioridade do motor. |

## Semântica do operador e cobertura existente

O modo da matriz científica é `operator_mode="synthetic_auto_accept"`. O evento
`OPERATOR_DECISION` transporta `decision="accept"`; no envelope de log, o campo
correspondente é `operator_decision`. O nome do evento não identifica uma pessoa.
O manifesto mantém `human_audit_status="pending"` e
`global_acceptance_status="pending"`. O caminho automático não aceita promover a
revisão humana a `complete` sem um processo humano verificável, ainda não implementado.

A inspeção dos testes existentes distingue os seguintes comportamentos:

- [test_every_selection_is_explained_then_accepted_before_service](../tests/test_dispatch_emulator.py)
  verifica a cadeia de aceitação automática antes do serviço.
- [test_replay_requires_matching_accepted_decision_before_service](../tests/test_digital_model_replay.py)
  introduz `decision="reject"` e espera erro. Isso verifica falha segura para um
  evento não suportado nesse modo; não é o ensaio de rejeição operacional.
- [test_operator_interventions.py](../tests/test_operator_interventions.py)
  exercita aceitar, rejeitar e substituir por outro candidato admissível, grava
  e relê JSONL e reconstrói o estado final. Rejeição não inicia serviço e mantém
  o recurso ocioso até um novo lote de eventos externos; override preserva a
  recomendação original e registra a escolha efetiva. Resposta ausente ou
  candidato ainda não chegado causa erro antes de qualquer serviço.

O ponto de entrada separado `run_synthetic_operator_trial` exige instância
`validation-` e uma função que retorne `SyntheticOperatorResponse` para cada
recomendação, sem aceitação implícita. Seu evento usa
`operator_mode="synthetic_scripted"`, `origin="simulated"`, motivo obrigatório
e versão de payload 1. Esses rastros são ensaios de engenharia; não são bundles
da matriz científica nem entram na exportação confirmatória de métricas ou H1.

Não há participação humana demonstrada no DES. A regra `fifo_override`
descreve uma quebra de FIFO causada pela política; não é uma sobreposição humana.
Fixtures com nomes de pessoas ou recibos `APPROVED` existem para testar limites do
software e nunca devem ser promovidas a avaliações reais.

## O que falta para as alegações pendentes

A rodada real de face deve produzir o recibo e as evidências previstos na rubrica.
A avaliação humana de A2 deve produzir sua própria amostra, julgamentos e trilha
de revisão. O fluxo com pessoas autorizadas ainda exige integração e avaliação;
os ensaios sintéticos não comprovam autenticação de operadores nem legibilidade
humana. A demonstração Unreal requer cena, ativos, importador e controles de
replay executáveis. A campanha principal depende dos pré-requisitos científicos e
de capacidade, seguida da execução, auditoria e análise de H1.

A evidência auxiliar de poder RHFS cobre um único Wilcoxon sobre contrastes
reamostrados. Ela não estima a potência da decisão completa de H1, que também exige
três comparadores, a guarda de throughput, o limiar de 15% e Holm entre estratos.
Os números arquivados não devem ser apresentados como resultados da campanha principal.
