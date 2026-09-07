# Catálogo rastreável das entradas sintéticas

Este catálogo reúne valores já declarados no protocolo e na implementação. Não
cria novos parâmetros, não emenda a configuração e não registra geração de
dataset ou execução de políticas. As tabelas abaixo descrevem um **desenho
sintético de engenharia**: os valores não são medições de um pátio, estimativas
ajustadas a observações reais nem calibração empírica validada. A validação de
face continua [PENDING](../inputs/face_validation_receipt.json).

## Fontes e natureza do suporte

Foram localizadas as matrizes de `main.tex`, a especificação e as configurações,
mas não um catálogo anterior com unidade, valor, origem e limite por parâmetro.
Este documento complementa a rastreabilidade desses artefatos:

- **C — configuração:** [confirmatory.json](../config/confirmatory.json), validada
  por [config.py](../src/pequiflux_experiment/config.py).
- **M — protocolo:** [main.tex](../../main.tex), seção de configuração do simulador,
  `sec:input-modeling` e tabelas `tab:plano-fatorial`, `tab:estratos-congestao-n`,
  `tab:parametros-experimentais`, `tab:parametros-politica` e
  `tab:rastreabilidade-fatos`.
- **S — especificação de implementação:** [seções 2, 4, 6 e 11](superpowers/specs/2026-09-02-notebook-experimental-completo-design.md).
- **G — geração:** [dataset.py](../src/pequiflux_experiment/dataset.py), especialmente
  `_resource_records`, `_build_event_latents`, `_build_instance`,
  `validate_candidate_semantics`, `plan_synthetic_dataset` e
  `select_pilot_configurations`.
- **D — domínio e realização:** [domain.py](../src/pequiflux_experiment/domain.py),
  `canonical_allowed_cargo_types`, e [emulator.py](../src/pequiflux_experiment/emulator.py),
  tratamento de `priority_change`, falhas e recuperação.

Nas tabelas, **H** significa hipótese numérica de engenharia; **R**, regra
estrutural do modelo; **A**, quantidade derivada aritmeticamente dessas escolhas;
e **I**, identificação ou limite computacional. C/M/S/G/D indicam a origem local
verificável do valor, não uma fonte empírica externa.

As referências já cadastradas em [refs.bib](../../refs.bib) têm alcance distinto:

| Referência existente | Suporte atribuído pelo protocolo | Limite da atribuição neste catálogo |
| --- | --- | --- |
| Law (2015), `lawSimulationModelingAnalysis2015` | Fundamentação metodológica de DES, escolha do detalhe e aproximação triangular; M cita seção 5.2 e páginas 376–377. | Não fornece evidência de que as tríades ou probabilidades deste projeto tenham sido medidas. A existência da citação não verifica por si o suporte quantitativo. |
| Berruto e Maier (2001), `r.berrutoAnalyzingReceivingOperation2001a` | Contexto de recebimento e diferentes grãos em elevador; M relaciona a discussão ao despejo isolado. | Apoio de domínio, não origem direta comprovada de `Tri(12,20,35)` nem de `Tri(2,4,7)`/`Tri(3,5,8)`. |
| Bouland (1967), `boulandTruckQueuesCountry1967a` | Contexto de filas e recebimento em elevadores de grãos. | Não transforma a decomposição sintética de atendimento em calibração de um pátio real. |

Nenhum valor numérico abaixo é classificado como extração bibliográfica direta.
Para fazer essa classificação no futuro será necessário associar cada valor a
trecho, página, unidade e condições da fonte. Esta revisão verifica a
rastreabilidade local; não substitui uma auditoria dos textos integrais. As
faixas narrativas de amostragem, despejo e ticket de M não são três sorteios
adicionais do gerador e não justificam somar etapas que não existem no modelo.

## Escala, relógio, recursos e fluxo

`Tri(a, moda, b)` denota uma distribuição triangular; os números são minutos,
exceto quando outra unidade estiver indicada. O relógio interno conta minutos
desde 06h00. Os suportes e probabilidades são especificações de entrada; uma
realização finita não precisa reproduzir exatamente suas frequências esperadas.

| Parâmetro | Unidade e valor congelado | Origem | Justificativa no desenho | Limite de interpretação |
| --- | --- | --- | --- | --- |
| Volume `truck_counts` | Caminhões/dia: 60, 120, 180 | H; C/M | Variar carga exógena em três níveis. | Não é demanda medida nem distribuição estimada de chegadas diárias. |
| Moegas `hopper_counts` | Recursos físicos: 1, 2, 3 | H; C/M | Variar capacidade de descarga e gargalo. | Não reproduz inventário de instalação real. |
| Balanças `scale_counts` | Recursos físicos: 1, 2 | H/R; C/M/D | Variar capacidade de um **pool compartilhado** entre pesagem inicial e final. | Não são dois pools independentes; o mesmo recurso físico fica indisponível para outra operação enquanto ocupado. |
| Portaria | Um recurso `gate-1` | R; M/G | Representar entrada com capacidade finita. | Capacidade fixa, fora do fatorial. |
| Horizonte `horizon_minutes` | 720 min, 06h00–18h00 | H/R; C/M | Dia terminante, com corte comum entre políticas. | Não há warm-up ou estado estacionário estimado; chegadas posteriores não são acrescentadas. |
| Estado inicial | Pátio e buffers vazios; recursos disponíveis | R; M/D | Condição inicial idêntica por réplica. | Não representa fila herdada do dia anterior. |
| Fim do dia | Corte em 720 min; remanescentes com espera censurada | R; M/D | Impedir throughput inflado por omissão da fila final. | Duração potencial previamente sorteada não significa serviço iniciado ou concluído no horizonte. |
| Fluxo | Quatro operações: `gate → scale_in → unload → scale_out` | R; C/M/G | Representar entrada, duas pesagens e atendimento na moega. | **Amostragem está embutida em `unload`**; não existe quinta operação autônoma de amostragem. |
| Buffer `buffer_capacity` | 12 caminhões em fila a jusante por etapa | H/R; C/M | Tornar bloqueio intermediário observável e limitar despacho. | Não é capacidade medida nem fila infinita; bloqueio continua obrigatório. |
| Tipos de carga | `soy` e `corn`; probabilidade 0,5 para cada caminhão | H; G | Introduzir mistura de produtos em condição controlada. | Não representa participação de mercado, safra ou composição real; 50/50 é probabilidade, não quota exata por instância. |
| Compatibilidade | Gate/balanças: ambas; `hopper-1`: ambas; `hopper-2`: só `soy`; `hopper-3`: só `corn` | R; D/G | Garantir pelo menos uma moega compatível e criar especialização quando há recursos adicionais. | Matriz sintética determinística; não extraída de planta industrial. Apenas os recursos do nível `m` existem. |
| Exposição à chuva | `hopper-1` exposta quando `m≥2`; moega única protegida | H/R; C/M/S/G | Permitir perturbação meteorológica sem fechamento estrutural de toda a descarga no caso de moega única. | Não descreve cobertura física observada. Especialização das outras moegas pode criar bloqueios de carga, que devem ser preservados. |

## Chegadas, tempos e atributos

| Parâmetro | Unidade e valor congelado | Origem | Justificativa no desenho | Limite de interpretação |
| --- | --- | --- | --- | --- |
| Blocos `arrival_blocks` | Minutos: `[0,180)`, `[180,300)`, `[300,480)`, `[480,720)`; pesos 6, 3, 7, 2 | H; C/M/S/G | Dois períodos de maior intensidade com `N` fixado externamente. | Peso é intensidade relativa: a probabilidade de bloco é proporcional a **peso × duração**, não apenas ao peso. |
| Chegadas no bloco | Uniforme dentro do bloco escolhido; ordenação `(arrival_minute, truck_id)` | H/R; S/G | Materializar `N` chegadas reprodutíveis sem alterar seu total. | É um processo condicionado a `N`, não ajuste empírico de um processo de Poisson ou taxa observada. |
| Pico `peak_arrival_weights` | Pesos 9, 2, 10, 2 nos mesmos blocos | H; C/M/S/G | Concentrar chegadas no regime `peak`. | Não muda `N`, níveis de recurso, duração de serviço ou estrato nominal. |
| Entrada `service_distributions.gate` | `Tri(2,4,7)` min | H; C/M | Variabilidade controlada da entrada. | Tríade assumida, sem estimativa empírica de parâmetros. |
| Pesagem inicial `scale_in` | `Tri(3,5,8)` min | H; C/M | Variabilidade da primeira visita à balança. | Suporte igual ao da pesagem final não implica mesmo sorteio ou mesmo tempo por caminhão. |
| Atendimento `unload` | `Tri(12,20,35)` min | H; C/M | Ciclo agregado de moega: amostragem, posicionamento/despejo e ticket. | Não é somente tempo de despejo; referências de grãos citadas em M não comprovam essa tríade como medição. |
| Pesagem final `scale_out` | `Tri(3,5,8)` min | H; C/M | Segunda visita ao pool físico de balanças. | Chave CRN própria da operação; disputa o mesmo pool de `scale_in`. |
| Prioridades `priority_probabilities` | `p2=0,15`, `p1=0,20`, `p0=0,65` | H; C/M/G | Misturar urgência mandatória, intermediária e ordinária. | Sorteio por caminhão: `u<0,15 → p2`; `0,15≤u<0,35 → p1`; demais `p0`. Não garante 15% exatos de mandatórios em uma réplica. |
| Bloqueio `document_block_probability` | Bernoulli 0,03 por caminhão | H; C/M/G | Exercitar a restrição documental antes do despacho. | Não é taxa de irregularidade observada. O evento não depende da política. |
| Liberação `document_release_distribution` | Duração candidata `Tri(30,60,120)` min | H/R; C/M/G | Tornar bloqueio temporário e rastreável. | Para bloqueados, o instante persistido é `min(720, chegada + duração)`; perto do corte, o atraso efetivo pode ser menor que a duração candidata. |
| Duração por caminhão/operação | Uma realização por cada uma das quatro operações | R; C/G | Congelar entradas antes de comparar políticas. | Sorteio durante geração, nunca durante `run_day`; não é uma duração por política ou por balança individual. |

## Regimes e perturbações

Os quatro regimes são `nominal`, `peak`, `critical_failure` e `priority_shift`.
Eles cruzam o mesmo fatorial de volume e recursos. “Nominal” não significa
ausência obrigatória de bloqueio documental, chuva ou falha-base.

| Parâmetro | Unidade e valor congelado | Origem | Justificativa no desenho | Limite de interpretação |
| --- | --- | --- | --- | --- |
| Falha-base `base_failure_probability` | Bernoulli 0,05 por instância/turno em `nominal`, `peak`, `priority_shift` | H; C/M/S/G | Introduzir uma possível indisponibilidade exógena. | É incidência de uma falha-base no sistema, **não 5% por recurso nem incidência da falha crítica forçada**. |
| Recurso da falha-base | Seleção uniforme na lista canônica: `gate-1`, `scale-1..b`, `hopper-1..m` | H/R; S/G | Remover a escolha implícita de recurso. | Decisão de engenharia explicitada em S; não é distribuição estimada de confiabilidade. |
| Início `failure_start_window` | `U(240,480)` min desde 06h00 | H; C/M/S/G | Introduzir indisponibilidade no período central do dia. | Instante **programado** congelado; realização pode ser adiada por atendimento em curso. |
| Duração `failure_duration_distribution` | `Tri(20,40,70)` min | H; C/M/S/G | Variar indisponibilidade sem alterar algoritmo de reparo entre políticas. | Não é MTTR estimado de manutenção real. |
| Falha crítica | Exatamente uma falha forçada em `critical_failure`; `hopper-1` se `36m≤72b`, senão `scale-1` | R/H; M/S/G | Perturbar o gargalo nominal, com empate resolvido a favor da moega. | Não sorteia Bernoulli adicional de falha-base. Início e duração ainda usam as distribuições acima. |
| Semântica da falha | Não preemptiva; início efetivo após serviço corrente, se ocupado; recuperação = início efetivo + duração congelada | R; M/S/D | Preservar atendimento em curso e causalidade. | Início efetivo e log podem divergir entre políticas mesmo com o mesmo candidato exógeno. |
| Instante `priority_shift_window` | `U(240,480)` min somente em `priority_shift` | H; C/M/S/G | Alterar urgência durante o dia. | Não depende da política ou de seu resultado. |
| Fração `priority_shift_fraction` | `ceil(0,10N)` IDs: 6, 12 ou 18 | H/R; C/M/S/G/D | Escolher antes das políticas a quantidade de eventos de promoção. | Seleciona caminhões com chegada ≥ instante, ordenados por `(chegada, truck_id)`; o DES fixa `p2`. IDs já `p2` podem estar entre os selecionados: a regra não promete 10% de **novos** mandatórios. |
| Falta de elegíveis para promoção | Rejeição da instância antes das políticas | R; G/S | Preservar a cardinalidade exigida. | Não reduz a fração, não muda a janela e não reamostra automaticamente para fazer a instância passar. |
| Chuva `rain_probability` | Bernoulli 0,10 por bloco elegível | H; C/M/S/G | Exercitar o fechamento de destino exposto. | Probabilidade de ativação por bloco, não probabilidade de chuva diária medida. |
| Bloco `rain_block_minutes` | 30 min; 24 blocos candidatos em `[0,720)` quando `m≥2` | H/R; C/M/S/G | Congelar a base temporal da perturbação. | Blocos ativos adjacentes são coalescidos; quantidade de linhas de perturbação não é igual a 24. |
| Precedência `event_ranks` | Ranks: conclusão 0; recuperação 10; fim de chuva 11; falha 12; início de chuva 13; liberação documental 20; promoção 21; chegada 30 | R; C/M/S | Resolver empates no mesmo instante sem depender da ordem incidental de inserção. | São códigos de ordenação, não tempos, prioridades humanas ou probabilidades. |

## Controles, identificação e execução

Estes valores não são novos dados exógenos do pátio. Permanecem separados para
que parâmetros de política, requisitos computacionais e critérios de análise
não sejam confundidos com medidas operacionais.

| Parâmetro | Unidade e valor congelado | Origem | Justificativa no desenho | Limite de interpretação |
| --- | --- | --- | --- | --- |
| Janela `ordinary_window` | `H0=6` candidatos ordinários por evento/recurso | H/R; C/M | Limitar reordenação local e manter justificativa auditável. | Não é ótimo calibrado; urgentes de pressão positiva seguem a regra de expansão. |
| Limiares `priority_thresholds` | Minutos: `tau0=60`, `tau1=30`, `tau2=10` | H; C/M | Definir pressão segundo prioridade. | Ordem no JSON é `[p0,p1,p2]`; não muda pelo piloto ou pelo desempenho observado. |
| Escore fixo | Pesos 0,45 espera normalizada; 0,35 prioridade; 0,20 afinidade imediata | H; M/S | Comparador determinístico previamente especificado. | Pesos de política, não probabilidades de geração nem ajuste posterior. |
| Políticas `policies` | `fifo_strict`, `fifo_flow_faithful`, `priority_local`, `fixed_score`, `lexicographic` | R; C/M | Comparação sobre a mesma instância exógena. | Cinco execuções não são cinco réplicas independentes da entrada; FIFO estrito permanece descritivo. |
| Sementes `seeds` | Inteiros 101–150; 50 por configuração | R; C/M | Pareamento reprodutível entre políticas. | Não são observações empíricas; identidade pareada inclui cenário e semente. |
| `crn_version` e `generation_attempt` | `crn.v1`; tentativa inicial 0 | R/I; C/G | Separar subfluxos aleatórios e rastrear reamostragem explícita de rejeitados. | Tentativa muda apenas em ação autorizada; não é retry oculto e não contém nome de política. |
| Piloto | `ceil(0,20×72)=15` configurações; 50 sementes e cinco políticas: 3.750 policy-days | H/R/A; M/S/G | Sanidade prévia com seleção determinística por hash. | Reutiliza entradas da grade completa; não remove casos da confirmação nem recalibra parâmetros. |
| Configuração declarada de validação | Índices `[20,12,24]`, semente `[101]`, cinco políticas | R; [validation.json](../config/validation.json) | Recorte declarado para checks, distinto da campanha principal e da demonstração mínima do notebook. | O notebook usa uma fixture de quatro caminhões e duas sementes. Nenhum desses recortes comprova materialização das 3.600 entradas ou execução dos 18.000 policy-days. |
| Guarda de throughput | `throughput_margin_rate=0,02`; mínimo 2 caminhões/dia; `delta(N)=max(2,0,02N)` | H/R; C/M | Definir a margem de não inferioridade por par. | Critério de decisão estatística, não variação da entrada para favorecer política. |
| Identificação | `project_name="PequiFlux - Experimento Reprodutivel"`; `protocol_version="1.0.0"`; `hypothesis="H1"` | I; C | Vincular manifestos à especificação. | Nomes e versões não demonstram validade científica ou aprovação humana. |
| `capacity.min_free_ram_gib` e `reserve_ram_gib` | 4 GiB livres mínimos; reserva de 2 GiB | I; C/S | Verificar capacidade antes da execução científica. | Limites de engenharia, não resultados observados da simulação. |
| `capacity.max_workers` e `receipt_ttl_seconds` | Até 4 workers; recibo válido por 60 s | I; C/S | Vincular concorrência autorizada à inspeção recente. | Workers também limitados pela CPU e RAM livres; não autorizam reduzir grade, sementes ou precisão. |
| `capacity.disk_margin` e `disk_reserve_gib` | Fator 1,25; reserva de 5 GiB | I; C/S | Margem sobre a estimativa de armazenamento da carga completa da fase. | Estimativa não comprova espaço realmente livre; exige inspeção. |
| `capacity.provider` e `cpu_only` | `cpu`; `true` | I; C/S | Fixar o caminho de execução suportado. | Inventário de GPU não implica utilização, aceleração ou substituição do algoritmo. |

## Cardinalidades previstas, sem geração

As contagens decorrem dos níveis de C, não de uma campanha executada:

| Quantidade | Derivação | Total previsto |
| --- | --- | --- |
| Configurações exógenas | `3 N × 3 m × 2 b × 4 regimes` | 72 |
| Instâncias de dia | `72 × 50 sementes` | 3.600 |
| Execuções política-dia | `3.600 × 5 políticas` | 18.000 |
| Caminhões únicos nas entradas | `(60+120+180) × 3 × 2 × 4 × 50` | 432.000 |
| Durações potenciais de serviço | `432.000 × 4 operações` | 1.728.000 |

O endereço de uma instância no desenho é `(scenario_index, seed)`; a realização
aceita também é identificada por `generation_attempt` e pelos hashes do dataset
e da instância. Um policy-day consome essa realização sem gerar outra. Durações potenciais incluem
serviços que podem nunca começar antes do corte; não são contagens observadas
de atendimentos. Rejeições, staging e tentativas explícitas podem conter outros
registros de trabalho: não devem ser somados ao total do dataset final completo.

O índice `rho=N/min(36m,72b)` deriva do horizonte de 720 minutos, da moda de
20 minutos na moega e das duas pesagens modais de 5 minutos no pool compartilhado.
É uma **aproximação nominal**, não utilização medida: não incorpora mistura de
cargas, especialização, chuva, falhas ou desempenho de política.

| Estrato | Regra congelada | Configurações | Pares cenário–semente previstos |
| --- | --- | --- | --- |
| `low` | `rho<0,70` | 4 | 200 |
| `medium` | `0,70≤rho<0,85` | 12 | 600 |
| `high` | `rho≥0,85` | 56 | 2.800 |

Os totais são 72 e 3.600. Os regimes não redefinem o estrato. Não há aqui
alegação de que esses pares já foram gerados, aprovados ou analisados.

## Pareamento CRN e pacote de entrada

A chave CRN implementada é
`(crn_version, scenario_index, seed, generation_attempt, entity_id, operation_or_event)`.
Ela não contém política. SHA-256 dos bytes canônicos da chave determina o
subfluxo usado para materializar chegadas, cargas, atributos, durações e
candidatos de evento antes da execução das políticas.

Assim, pareamento significa **mesmas entradas exógenas**. Ordem de despacho,
filas, utilização, instante efetivo de falha não preemptiva, métricas e logs
finais podem diferir entre políticas. Igualdade do log ou do estado final de
políticas distintas não é um requisito de CRN. Replay, por sua vez, deve
reconstruir o log da própria execução que recebeu, sem reamostrar a entrada.

O contrato de G contém exatamente seis payloads obrigatórios:

| Payload | Conteúdo | Cardinalidade e limite |
| --- | --- | --- |
| `scenario_index.parquet` | Fatores, índice/ID, `rho`, estrato e identidade de configuração | 72 linhas previstas no dataset completo. |
| `trucks.parquet` | Identidade, chegada, carga, prioridade, documento e estado inicial | 432.000 caminhões previstos; não logs de serviço. |
| `service_times.parquet` | Duração potencial por caminhão/operação, tríade de origem e chave CRN | 1.728.000 durações previstas; quatro operações. |
| `disruptions.jsonl` | Perturbações realizadas na entrada, com referência ao candidato exógeno | Quantidade variável: incidências sorteadas e coalescência de chuva. Não confundir com eventos finais do DES. |
| `event_latents.jsonl` | Candidatos congelados de documento, falha-base, promoção, chuva e falha forçada | Cardinalidade segue o catálogo de candidatos elegíveis; candidato não implica evento ativo. |
| `rejection_log.jsonl` | Razões e proveniência de rejeições | Depende do histórico; não produz aprovação ou reamostragem automática. |

`manifest.json` registra configuração completa, versão do gerador, runtime,
identidade das instâncias e hashes dos seis payloads. `checksums.sha256`
contém as seis entradas canônicas. `FREEZE.json` liga `manifest_hash`,
`checksums_hash` e `dataset_root_hash`; o carregador recalcula a cadeia e
confere o pin externo `expected_dataset_root_hash` fornecido pela ação.
O hash raiz não pode ser aceito apenas porque o próprio dataset o declara.
Arquivo ausente, hash divergente, cardinalidade incompatível ou pacote antigo
de cinco payloads impede seu uso como entrada científica válida.

A quantidade de eventos executados no DES é variável e depende das entradas,
da política, dos bloqueios e do horizonte. Não deriva de `4×N` e não pode ser
preenchida com as contagens potenciais acima.

## Lacunas de evidência que permanecem

Falta uma base longitudinal real para estimar distribuições, probabilidades e
correlações. A documentação local também não oferece uma extração quantitativa
por página que sustente as tríades e taxas como valores bibliográficos diretos.
Em particular, a mistura 50/50 e a especialização das moegas estão codificadas
em G/D, fora dos campos de C; sua origem é uma decisão estrutural de engenharia.

A tabela de fatos operacionais de M registra categorias de origem, mas não
constitui medição desses parâmetros. A aprovação humana de face ainda falta e
não deve ser substituída por fixtures. Também não foi gerado ou simulado o
dataset principal nesta revisão. Qualquer futura mudança de valor, distribuição
ou semântica deve seguir a emenda do protocolo e as gates existentes, sem
reclassificar os valores atuais como dados calibrados.
