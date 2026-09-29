# Academic Paper: Logistics 5.0 in Agro-Industrial Yard Dispatching

Este diretório contém o manuscrito canônico do artigo científico derivado do TCC, formatado para submissão à revista **Production** (ABEPRO / SciELO).

## Informações Editoriais

- **Periódico Alvo**: *Production* (Associação Brasileira de Engenharia de Produção - ABEPRO / SciELO)
- **Tipo de Submissão**: *Original Research Article*
- **Idioma**: Inglês
- **Enquadramento Temático**: *Logistics 5.0 in Production Engineering*
  - **Foco Humano (Human-Centricity)**: Mecanismo de recomendação explicável, auditável e aberto à intervenção supervisionada de operadores (Critério A2).
  - **Resiliência Operacional**: Reação contínua a eventos disruptivos (chuva em moegas descobertas, quebras mecânicas de tombadores, bloqueios documentais e alterações de prioridade contratual).
  - **Transformação Digital**: Integração do simulador de eventos discretos (DES) reprodutível a um modelo digital 3D (Unreal Engine 5.8) alimentado por logs padronizados JSONL.
- **Metodologia**: Design Science Research (DSR).

## Estrutura de Arquivos

```text
paper/
├── README.md             # Esta documentação
├── manuscript.tex        # Texto canônico do artigo científico em LaTeX (inglês)
├── refs.bib              # Base bibliográfica canônica do artigo
├── latexmkrc             # Configuração de compilação isolada (saída em build/)
└── build/                # Artefatos intermediários e PDF gerado (manuscript.pdf)
```

## Compilação

Para compilar o artigo gerando `build/manuscript.pdf`:

```bash
cd paper
latexmk -xelatex manuscript.tex
```

Ou usando o compilador padrão configurado pelo `latexmkrc` local:

```bash
latexmk manuscript.tex
```

## Relação com o TCC e Repositório

- O texto canônico da monografia (em português) permanece em `../main.tex`.
- O pacote experimental, testes e gerador sintético estão em `../experimento-notebook/`.
- Os esquemas conceituais (layout do pátio, fluxo reentrante e arquitetura DES) são renderizados em código nativo TikZ diretamente no manuscrito, garantindo resolução vetorial e independência de imagens externas rasterizadas.
