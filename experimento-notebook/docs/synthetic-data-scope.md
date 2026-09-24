# Escopo fechado das entradas sintéticas

Este contrato complementa a [especificação experimental](superpowers/specs/2026-09-02-notebook-experimental-completo-design.md)
e o [catálogo de parâmetros](synthetic-input-catalog.md). Plausibilidade sintética
não equivale a calibração com dados reais. A [emenda v2](protocol-v2-amendment.md)
trata parâmetros como hipóteses de engenharia e registra avaliação humana não
realizada. O recibo de face v1 permanece histórico; sua aprovação não é requisito
de geração ou execução v2.

## Unidade e dimensão previstas

Uma realização exógena é identificada por configuração, semente e tentativa
de geração (`generation_attempt`), dentro de um dataset identificado por hash.
O identificador do par cenário/semente é um endereço no desenho; a tentativa
e o hash da instância distinguem suas realizações. As cinco políticas recebem
a mesma instância aceita. Esperas, throughput, ganhos e demais saídas são
calculados pelo DES; não são entradas fabricadas.

| Quantidade prevista | Derivação |
| --- | --- |
| 72 configurações | 3 volumes × 3 moegas × 2 balanças × 4 regimes |
| 50 sementes | 101 a 150 |
| 3.600 instâncias exógenas | 72 × 50 |
| 18.000 execuções de política | 3.600 × 5 |
| Baixa / média / alta carga | 4 / 12 / 56 configurações; 200 / 600 / 2.800 pares |
| 432.000 caminhões | (60 + 120 + 180) × 3 × 2 × 4 × 50 |
| 1.728.000 durações potenciais | 432.000 × 4 operações |

Essas são cardinalidades do plano puro `plan_synthetic_dataset`; não atestam
materialização nesta revisão. `DatasetPlan.truck_count` e
`potential_service_time_count` não multiplicam entradas pelas políticas.
Disrupções realizadas e rejeições têm cardinalidade variável. Um dataset
materializado exige verificação dos payloads e da cadeia de hashes.

## Fronteiras do modelo e verificações

O dia é terminante, de 0 a 720 minutos. O pátio e os buffers começam vazios;
o inventário de caminhões futuros não significa caminhões presentes no pátio.
O fluxo é `gate → scale_in → unload → scale_out`: as duas pesagens compartilham
as mesmas balanças físicas. A amostragem está abstraída no ciclo de descarga,
sem quinta operação.

| Entrada | Verificação exigida |
| --- | --- |
| Chegadas | Exatamente N; horários no horizonte; perfil nominal/pico por blocos; plausibilidade agregada sem selecionar sementes por desempenho. |
| Serviço | Quatro durações finitas por caminhão, dentro do suporte triangular; chaves CRN independentes da política. |
| Carga e prioridade | Compatibilidade por recurso; classes 0/1/2 e promoção congeladas; regra mandatória e desempates preservados. |
| Documentos | Bloqueio impede despacho. Espera em fila conta apenas tempo elegível; retenção documental é separada e integra o tempo no sistema. |
| Recursos e buffer | Precedências, exclusão mútua e pool físico compartilhado; reservas e ocupação respeitam a capacidade 12 no principal. |
| Falhas | Distinguir variável latente, gatilho realizado e início efetivo; falha crítica no gargalo; serviço em curso não é preemptado. |
| Chuva | Blocos de 30 minutos e cobertura por layout; blocos contíguos coalescidos; união das indisponibilidades e recuperação verificáveis. |
| Corte final | Serviço ou fila em curso é censurado em 720; nenhum término futuro conta no throughput observado. |
| Intervenções | Ensaios sintéticos separados para aceitar, rejeitar e substituir por candidato admissível; nenhuma resposta pode ultrapassar restrições rígidas. Origem simulada explícita, sem aprovação humana implícita. |

As validações de entradas estão em [dataset.py](../src/pequiflux_experiment/dataset.py)
e [domain.py](../src/pequiflux_experiment/domain.py). A execução usa o
[DES](../src/pequiflux_experiment/emulator.py), com reconstrução dos estados e
[auditoria](../src/pequiflux_experiment/audit.py). Os ensaios de intervenção
usam uma entrada específica de validação; não integram a matriz científica
com aceitação sintética automática.

O ponto de entrada `run_synthetic_operator_trial(..., operator_script=...)`
aceita apenas instâncias com identificador `validation-`. A função fornecida
retorna `SyntheticOperatorResponse("accept", motivo)`,
`SyntheticOperatorResponse("reject", motivo)` ou
`SyntheticOperatorResponse("override", motivo, selected_truck_id=...)`.
Override exige outro candidato do conjunto admissível oferecido; rejeição
aguarda novo lote de eventos externos. Os [testes de intervenção](../tests/test_operator_interventions.py)
verificam comandos, bloqueio de escolhas inadmissíveis e replay do JSONL
persistido. A interface humana e sua avaliação permanecem pendentes.

## Persistência e CRN

```text
dataset/<DATASET_ID>/
  scenario_index.parquet
  trucks.parquet
  service_times.parquet
  disruptions.jsonl
  event_latents.jsonl
  rejection_log.jsonl
  manifest.json
  checksums.sha256
  FREEZE.json
```

O caminho é organizacional; os seis payloads e suas semânticas permanecem
canônicos. Não há migração para CSV. O manifesto identifica parâmetros,
versões, cardinalidades observadas e hashes. `FREEZE.json` só pertence a um
dataset que passou pelas verificações de publicação.

A chave CRN não inclui política. Entradas e variáveis latentes congeladas
devem ser iguais, assim como a regra que as transforma em eventos físicos.
Logs finais não precisam ser idênticos: decisões alteram filas, inícios de
serviço e o adiamento não preemptivo de falhas. Igualdade de resultados não
é um requisito de CRN e superioridade de uma política não valida o dataset.

Rejeição usa somente critérios estruturais anteriores à execução de políticas.
A geração aborta e preserva staging e motivos; não troca silenciosamente a
semente. A reamostragem científica é uma ação explícita, com nova tentativa,
namespace e `resample_provenance.json`, conservando os aceitos conforme o
contrato existente. Retentar I/O não autoriza reamostrar, substituir dados
nem ocultar a falha original.
