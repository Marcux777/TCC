# Contrato das métricas canônicas

`compute_policy_day_metrics(persisted_day) -> MetricRow` é a única produtora
oficial. A entrada é um JSONL já gravado, com inventário inicial, controles e
modalidade de admissão explícitos. `DayResult` contém eventos e evidências
físicas, sem métricas. O runner vincula o `MetricRow` ao SHA-256 desses mesmos
bytes antes de publicar a linha de resultados. O esquema das métricas é 2 e o
manifesto de execução é 4; os nomes antigos não são aliases aceitos.

Cada campo escalar, por recurso e por caminhão possui definição, unidade,
população e janela em `METRIC_CATALOG`, em `src/pequiflux_experiment/metrics.py`.
Esse catálogo acompanha `MetricRow.definitions.catalog` e as exportações
`table_metric_catalog.csv` e `table_metric_assumptions.csv`. Ele é declarativo:
o auditor compartilha os descritores, mas reconstrói os valores por outro
algoritmo, a partir do inventário e dos eventos replayados. Compara todos os
escalares e detalhes com o JSON e o CSV, incluindo os hashes. Recalcular usando
a função produtora não constitui essa segunda reconstrução.

## Espera, documentos e corte

A observação é o intervalo de 0 a 720 minutos. Para cada caminhão, a espera
de fila acumula os intervalos entre estar liberado documentalmente para a
etapa e iniciar seu atendimento, nas quatro operações: portaria, pesagem de
entrada, descarga e pesagem de saída. Recurso ocupado, fila ou buffer cheio
não interrompem essa espera. Tempo em atendimento não é espera.

Na portaria, a elegibilidade começa na chegada se os documentos estão
liberados; caso contrário, começa na liberação documental. Nas etapas
seguintes, começa na conclusão da operação anterior. A retenção documental
é medida separadamente, da chegada à liberação, limitada ao horizonte.
`document_hold_minutes` não é somada à espera primária de H1.

Se o caminhão ainda aguarda atendimento aos 720 minutos e está liberado
documentalmente, o intervalo entre sua última elegibilidade e o corte entra
em `wait_minutes` e em `censored_wait_minutes`. Se está em serviço, registra-se
somente a parte observada desse serviço; se continua documentalmente bloqueado,
registra-se a retenção até o corte. Não se gera uma conclusão artificial.
Por caminhão, vale:

`tempo observado no sistema = espera de fila + serviço observado + retenção documental`.

As estatísticas de espera usam todos os caminhões do inventário, inclusive os
inacabados. A média é aritmética, p50 é a mediana aritmética, p95 é o elemento
de posição `ceil(0.95*N)` na lista ordenada, com posição começando em 1. O IQR
usa quartis com interpolação linear R7. Para `[0, 2, 4, 6]`, a média e p50 são
3, p95 é 6 e IQR é 3. A espera é acumulada por caminhão antes de calcular os
quantis; não se misturam intervalos individuais das etapas nessa população.

Os resumos de tempo de ciclo completo usam apenas caminhões cuja pesagem de
saída terminou até 720. Os demais conservam o tempo chegada–720 e o indicador
`system_time_censored`. As contagens de ciclos completos e censurados devem
acompanhar os resumos condicionais.

## Produção e intervalo observado

| Campo | Definição e unidade |
|---|---|
| `throughput` | Quantidade inteira de caminhões concluídos no dia operacional de 720 minutos; igual a `completed_trucks`. |
| `throughput_per_hour` | `throughput / 12`, em caminhões por hora observada. |
| `remaining_trucks` | Inventário menos caminhões concluídos, em caminhões. |
| `observed_makespan_minutes` | Última conclusão de qualquer etapa observada no horizonte menos primeira chegada, em minutos. |

O makespan observado descreve o intervalo de atividade que terminou dentro
do corte. Seu último evento pode ser a pesagem de entrada de um caminhão
inacabado. Ele não estima o instante em que toda a fila será atendida.
`completed / observed_makespan` não é throughput por dia nem a taxa horária
canônica. H1 continua usando a contagem de conclusões, com margem em caminhões.

## Recursos e máximos

Para cada recurso, com horizonte `H=720`, os intervalos são limitados a `H`:

- `busy`: tempo de serviço, incluindo a parte observada de serviços inacabados;
- `down`: união das indisponibilidades efetivas, sem duplicar causas sobrepostas;
- `available = H - down`;
- `idle = available - busy`, excluindo indisponibilidade;
- utilização bruta: `busy/H`; utilização líquida: `busy/available`;
- fração ociosa bruta: `idle/H`; fração ociosa líquida: `idle/available`.

Ocupação e indisponibilidade não podem se sobrepor na execução não preemptiva.
Por recurso, `busy + down + idle = H`. Agregações por recurso/classe usam somas
de recurso-minutos nos numeradores e denominadores, nunca a média simples de
porcentagens individuais. Quando `available=0`, a utilização líquida é
indefinida e a produção do `MetricRow` falha explicitamente.

`scale_occupancy_peak` é o máximo de serviços simultâneos no pool compartilhado
de balanças. `max_queue_length` é o máximo de caminhões aguardando em uma das
quatro filas; a fila da portaria inclui retenções documentais.
`max_buffer_occupancy` conserva a convenção física do buffer: máximo entre as
três filas internas e a reserva de entrada. `max_buffer_reservation` é o máximo
entre as reservas de entrada e saída. Entrada conta caminhões em pesagem de
entrada ou descarga, ativos ou enfileirados; saída conta descargas ativas e
caminhões na fila de pesagem de saída. Começar a pesagem de saída libera a
reserva. Esses quatro máximos têm unidade caminhões e não são utilizações
temporais. Não se somam reservas dos dois buffers para testar o limite de um.

## Estabilidade, FIFO e admissão

O desempate de FIFO usa `(stage_entry_time, truck_id)`. `fifo_break_count`
compara a seleção com o primeiro caminhão da fila admitida registrada, e sua
taxa divide essa contagem pelo número de recomendações. A justificativa
persistida deve concordar com a reconstrução.

`raw_fifo_break_count` considera a fila do mesmo tipo físico de recurso antes
dos filtros documentais, de carga, buffer e prioridade obrigatória.
`avoidable_fifo_break_count` conta somente as quebras dessa referência em que
o primeiro caminhão podia ser atendido sob as mesmas restrições rígidas e
obrigatórias. O auditor reconstrói esses fatos; o nome da política não é
evidência de intenção ou evitabilidade.

`RUN_STARTED.admission_mode` registra `full_queue` ou `mandatory_window`.
Esse modo, os controles e o estado observado determinam os candidatos admitidos.
Contagens de janela H0, prioridade obrigatória e expansão crítica medem
ativações ou exposições de candidatos em recomendações. Um caminhão observado
em várias decisões conta várias vezes; esses campos não contam caminhões únicos.

Estabilidade compara listas consecutivas de candidatos do mesmo recurso,
restritas aos identificadores comuns. Conta pares invertidos e deslocamentos
absolutos de posição. O deslocamento médio é a média das médias de cada
comparação; interseções vazias ou unitárias têm distância zero. O número de
comparações e as exposições de candidatos comuns acompanham o resultado.
`replanning_count` conta comparações com inversão; sua frequência divide por
12 horas. São mudanças observadas de ordem, sem inferir execuções de um
otimizador ou intervenções humanas. Aceites/rejeições registram os eventos do
operador; aceite sintético não é validação humana.

## CO₂ como hipótese exploratória

`CO2_estimado = (total_wait_minutes/60) × engine_on_fraction × idle_fuel_rate × diesel_factor`.

O valor-base usa 0,8 galão americano por hora e 10,18 kg CO₂ por galão
americano. O primeiro é uma referência aproximada para caminhões pesados de
longa distância publicada pelo [DOE em 2015](https://afdc.energy.gov/uploads/publication/hdv_idling_2015.pdf).
O fator de diesel vem da [Tabela 1 da documentação SmartWay da EPA, 2024](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P101961J.txt),
que pressupõe oxidação completa do combustível.

`engine_on_fraction=1.0` é uma hipótese do projeto: o motor permanece ligado
durante toda a espera elegível. Não é um dado observado nem um valor estimado
para este pátio. Os cenários de 0,5 e 1,0 galão americano/hora também são
hipóteses de sensibilidade, não limites medidos. Fontes, unidades e condição
de hipótese ficam no sidecar e na tabela de premissas exportada.

O cálculo inclui a espera elegível observada até o corte. Exclui retenção
documental, deslocamento, partida a frio, poeira, eletricidade e ciclo de vida
do combustível. É estimativa exploratória de CO₂ da combustão, não emissão
medida, inventário completo do pátio ou componente confirmatório de H1.

## Verificação e ausência de dados

`tests/test_metrics.py` contém trajetórias analíticas e expectativas numéricas,
incluindo `[0,2,4,6]`, censura, documentos, recursos, filas, FIFO e denominadores
nulos. O auditor reconstrói essas famílias independentemente e os testes de
auditoria adulteram métricas e hashes de forma coerente para verificar a
reconciliação semântica. O teste de desacoplamento impede que a auditoria use
o produtor oficial como oráculo.

Contagem observada igual a zero é válida. Campo ausente, evento obrigatório
ausente, quebra de integridade, denominador nulo ou população necessária vazia
geram erro explícito. Sem ciclos completos, seus quantis são indefinidos; sem
decisões ou comparações consecutivas, as respectivas taxas são indefinidas.
O log permanece como evidência, mas não se publica uma linha parcial com zero,
`None`, `NaN` ou sucesso artificial. Valores publicados são arredondados a 12
casas decimais; arredondamento não substitui a reconstrução dos intervalos.
