# Projeto experimental reproduzível em notebook

**Data:** 2026-09-01  
**Status:** desenho aprovado em chat; aguardando revisão desta especificação  
**Local:** `experimento-notebook/`

## Objetivo

Criar um projeto Python autocontido, dentro do repositório atual, para implementar e demonstrar o protocolo experimental do TCC por meio de um notebook central reexecutável. O projeto deve reconstruir o protótipo, validar suas invariantes, executar uma demonstração determinística, executar ou carregar explicitamente uma campanha experimental e regenerar as análises, tabelas e figuras sem depender de estado oculto.

O notebook será a interface principal para leitura, demonstração e reprodução. A implementação permanecerá em módulos locais pequenos e testáveis, todos dentro de `experimento-notebook/`. Não haverá importação do repositório adjacente `agro-yard-des-experiment`, cópia automática de artefatos externos nem alteração dos arquivos já existentes na raiz do TCC.

## Fronteiras científicas

- O artefato será chamado de **modelo digital**, não de gêmeo digital. Não há ativo físico individual pareado, telemetria contínua nem sincronização bidirecional operacional.
- H1 permanece a hipótese comparativa. A1 e A2 permanecem critérios de aceitação do artefato.
- A consistência entre o emulador e o estado digital será medida como diagnóstico de engenharia. Ela não será promovida a um novo critério confirmatório A3 sem emenda explícita do protocolo do TCC.
- Execuções de validação, demonstração, piloto e confirmação terão namespaces e manifestos distintos. Nenhuma delas poderá ser apresentada como outra fase.
- Resultados ausentes ou incompletos não serão fabricados, preenchidos com valores padrão nem substituídos por resultados de outra execução.

## Estrutura

```text
experimento-notebook/
├── TCC_experimentos.ipynb
├── README.md
├── pyproject.toml
├── config/
│   └── confirmatory.json
├── src/pequiflux_experiment/
│   ├── __init__.py
│   ├── config.py
│   ├── domain.py
│   ├── events.py
│   ├── emulator.py
│   ├── digital_model.py
│   ├── dispatch.py
│   ├── policies.py
│   ├── audit.py
│   ├── experiment.py
│   ├── statistics.py
│   └── export.py
├── tests/
├── runs/
└── results/
    ├── raw/
    ├── processed/
    ├── tables/
    └── figures/
```

Código, configuração, testes e notebook serão versionáveis. Saídas volumosas de execução ficarão fora do conteúdo incorporado ao notebook. O repositório manterá apenas artefatos pequenos que forem deliberadamente selecionados para reprodução ou apresentação.

## Componentes e responsabilidades

### Configuração e manifesto

`config.py` carregará `config/confirmatory.json` em estruturas imutáveis, validará todos os campos e calculará um hash canônico da configuração. Não existirão números experimentais importantes espalhados pelo notebook.

Cada execução criará `runs/<run_id>/manifest.json`. O identificador combinará fase, instante UTC, versão do protocolo, commit Git e hash abreviado da configuração. A pasta deverá ser nova; uma colisão interromperá a execução em vez de sobrescrever resultados.

O manifesto registrará, no mínimo:

- projeto, protocolo, fase e hipótese;
- commit Git e estado limpo ou sujo do checkout;
- versão do Python, sistema operacional e dependências relevantes;
- CPU, memória e GPU detectadas, sem exigir GPU para a execução comum;
- sementes, políticas, configuração e respectivos hashes;
- comando ou perfil executado;
- caminhos dos artefatos produzidos.

### Domínio e eventos

`domain.py` definirá tipos explícitos para caminhões, recursos, filas, etapas, intervenções e recomendações. `events.py` definirá eventos imutáveis, sua ordenação determinística e a forma canônica serializável.

Não serão usados dicionários de formato variável como estado central. A serialização poderá usar dicionários apenas na fronteira de persistência, depois de validação estrutural.

### Emulador e modelo digital

`emulator.py` será a contraparte física experimental: relógio, lista futura de eventos, chegadas, serviços, recursos, falhas, chuva, bloqueios e comandos executados.

`digital_model.py` manterá estado próprio e será atualizado exclusivamente pelos eventos públicos emitidos pelo emulador. Emulador e modelo digital não compartilharão instâncias mutáveis. Uma recomendação será produzida a partir de um instantâneo do estado digital, passará por uma decisão de operador explícita e só então se tornará comando para o emulador.

O fluxo será:

```text
emulador -> evento serializável -> estado digital
estado digital -> recomendação -> decisão do operador
decisão do operador -> comando validado -> emulador
```

### Despacho e políticas

`dispatch.py` separará construção de candidatos factíveis, restrições rígidas, domínio admissível, ranqueamento, explicação e emissão de recomendação. O despacho não alterará diretamente o emulador.

`policies.py` oferecerá uma única interface para as cinco políticas do painel principal:

- FIFO estrito;
- FIFO flow-faithful;
- prioridade com factibilidade local;
- escore fixo;
- política lexicográfica proposta.

Todas receberão o mesmo instantâneo observável e serão executadas sob as mesmas sementes e cenários. Informações futuras ou durações realizadas não estarão disponíveis para nenhuma política.

### Auditoria e replay

Cada decisão gerará um registro JSONL com identificadores de execução, cenário, semente, evento, instante, recurso, candidatos, exclusões justificadas, seleção, política, explicação, decisão humana e hashes do estado antes e depois.

`audit.py` lerá somente os artefatos persistidos. Ele verificará integridade estrutural, A1, completude automatizável de A2, monotonicidade temporal, hashes, presença dos logs e consistência entre resultados agregados e decisões. A inspeção humana de A2 continuará explicitamente pendente até ser realizada e registrada.

O replay reconstruirá o estado digital a partir do JSONL e comparará o estado final canônico. Eventos perdidos, duplicados, fora de ordem ou incompatíveis interromperão a validação com o evento e a causa originais.

### Execução experimental

`experiment.py` exporá uma única função de matriz que receba cenários, políticas, sementes, configuração e diretório novo de execução. Ela persistirá resultados progressivamente e validará a grade pareada antes de liberar análise confirmatória.

O notebook terá um único seletor explícito:

```python
RUN_PROFILE = "validation"
```

Perfis permitidos:

- `validation`: testes, casos de sanidade e matriz mínima determinística; produz apenas evidência de engenharia;
- `pilot`: executa a amostra piloto pré-especificada em namespace próprio;
- `load-confirmatory`: carrega um `CONFIRMATORY_RUN_ID` explícito e falha se o pacote não estiver completo;
- `execute-confirmatory`: executa a matriz confirmatória completa em uma pasta nova, depois dos gates de protocolo e capacidade.

Não haverá seleção automática de perfil, busca pelo resultado “mais recente”, recomputação implícita, retry nem fallback de `load-confirmatory` para `execute-confirmatory`.

Antes de `execute-confirmatory`, o notebook verificará capacidade e propriedade dos recursos locais. Ele não iniciará a carga sustentada se um recurso obrigatório estiver ausente, se a aceleração suportada não preservar equivalência ou se outro processo já possuir o recurso requerido. A execução completa não fará parte da validação cotidiana por `Run All`.

### Estatística e decisão de H1

`statistics.py` trabalhará apenas sobre uma grade pareada integral e um único hash de protocolo. A saída incluirá mediana, IQR, diferenças pareadas, melhoria percentual, Wilcoxon unilateral, Hodges--Lehmann, bootstrap pareado, tamanho de efeito, guarda de throughput e a decisão conjuntiva de H1 por estrato e comparador.

A função de decisão retornará estados estruturados como `SUPPORTED`, `NOT_SUPPORTED` ou `INVALID_INPUT`. Ela não inferirá sucesso a partir de resultados parciais e não permitirá agregação geral substituir a decisão separada em média e alta congestão.

### Exportação

`export.py` gerará tabelas CSV, dados analíticos Parquet e figuras PDF/PNG diretamente dos resultados processados. A ausência do mecanismo Parquet declarado será um erro de dependência; não haverá troca silenciosa de formato.

Os principais caminhos serão:

```text
results/raw/experiment_runs.parquet
results/raw/decision_logs.jsonl
results/processed/summary.parquet
results/tables/table_h1.csv
results/tables/table_throughput.csv
results/tables/table_audit.csv
results/figures/p95_by_policy.pdf
results/figures/paired_improvement.pdf
results/figures/throughput_waiting_tradeoff.pdf
```

## Organização do notebook

`TCC_experimentos.ipynb` terá células lineares e idempotentes, nesta ordem:

1. identificação, manifesto e perfil de execução;
2. carregamento e validação da configuração congelada;
3. inventário do ambiente;
4. apresentação do domínio e da arquitetura;
5. execução dos testes automatizados por um único comando;
6. cenários de sanidade;
7. demonstração emulador -> modelo digital -> recomendação -> comando;
8. replay e auditoria da demonstração;
9. piloto ou campanha escolhida pelo perfil;
10. carregamento dos artefatos persistidos;
11. análise estatística e decisão estruturada de H1;
12. diagnósticos de consistência do modelo digital;
13. tabelas e figuras finais;
14. resumo de artefatos e limites das conclusões.

Nenhuma célula dependerá de execução manual anterior. Outputs extensos serão resumidos, e logs completos ficarão em arquivo.

## Dependências e execução

O projeto declarará Python 3.11 ou superior e as dependências necessárias para arrays, tabelas, estatística, Parquet, figuras, testes e execução programática do notebook. As versões serão limitadas no `pyproject.toml`; um arquivo de lock será criado somente com ferramenta já disponível e sem instalar ou atualizar pacotes implicitamente.

O README documentará criação do ambiente, instalação deliberada pelo usuário, execução dos testes, execução limpa do notebook e seleção dos perfis. Se uma dependência ou executável estiver ausente, o comando falhará com o nome da operação, o requisito e a exceção causal.

## Estratégia de testes

O projeto usará o menor conjunto de testes que cubra os riscos materiais distintos:

1. **restrições e despacho:** candidato bloqueado ou recurso indisponível nunca produz comando executável;
2. **isolamento e replay:** emulador e modelo digital não compartilham estado, e o JSONL reconstrói o mesmo estado final;
3. **determinismo e pareamento:** a mesma configuração e semente geram artefatos canônicos equivalentes, e uma célula ausente ou duplicada invalida a análise;
4. **decisão científica:** H1 e a guarda de throughput são julgadas segundo a regra conjuntiva em dados sintéticos controlados;
5. **notebook:** uma execução limpa do perfil `validation` conclui sem erro e produz o conjunto mínimo de artefatos declarado.

Os cinco checks cobrem invariantes diferentes: segurança, separação de estado, reprodutibilidade, integridade inferencial e jornada executável. Testes adicionais exigirão um novo risco material, não uma meta abstrata de cobertura.

## Tratamento de erros

Toda fronteira será fail-fast. Erros preservarão a causa original e incluirão operação, run id, configuração, semente ou artefato pertinente. São bloqueadores explícitos:

- configuração inválida ou divergente;
- dependência ausente;
- pasta de execução já existente;
- grade pareada incompleta ou duplicada;
- mistura de hashes de protocolo;
- log ausente, corrompido ou fora de ordem;
- divergência de replay;
- violação de restrição rígida;
- tentativa de análise confirmatória sobre piloto ou validação;
- tentativa de executar a campanha completa sem os gates de capacidade.

Não haverá exceções engolidas, retries automáticos, valores de sucesso padrão ou seleção de artefato alternativo.

## Critérios de aceitação

O projeto estará implementado quando:

- todo o conteúdo novo estiver contido em `experimento-notebook/`;
- não houver importação do repositório experimental adjacente;
- o perfil `validation` executar o notebook do início ao fim em ambiente compatível;
- os testes dos cinco riscos materiais passarem sem retry;
- a demonstração produzir manifesto, métricas, JSONL, replay e auditoria coerentes;
- o perfil `load-confirmatory` falhar claramente quando o run id estiver ausente ou incompleto;
- tabelas e figuras forem regeneradas apenas a partir de artefatos persistidos;
- README e notebook distinguirem validação, piloto e confirmação;
- nenhuma saída for apresentada como evidência confirmatória sem uma campanha confirmatória completa e auditada.

## Fora de escopo

- integração ou importação de código do repositório adjacente;
- execução automática das 18.000 corridas durante desenvolvimento;
- instalação automática de dependências;
- alteração do protocolo canônico em `main.tex`;
- implementação do Unreal Engine;
- uso de internet ou APIs externas durante o notebook oficial;
- alegação de gêmeo digital ou validação operacional de campo.
