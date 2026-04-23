# TCC em LaTeX

Projeto LaTeX baseado no arquivo de refer\^encia `PROJETO TCC Marcus Vinicius.docx`, com margens A4 equivalentes, imagem institucional extra\'ida do documento e capa/folha de rosto ajustadas para ficar visualmente pr\'oximas do original.

## Arquivos principais

- `main.tex`: documento principal.
- `images/puc-goias.png`: imagem extra\'ida do `.docx`.
- `build/`: sa\'ida da compila\c{c}\~ao.

## Como compilar

```bash
latexmk -xelatex main.tex
```

## Informacoes tecnicas do TCC I (`CMP1071`)

Esta secao foi ajustada para o que interessa tecnicamente ao `TCC I` de Ciencia da Computacao na PUC Goias. Os pontos abaixo combinam:

- regras oficiais do PPC do curso; e
- a estrutura atualmente implementada neste repositorio em `main.tex`.

### Enquadramento da disciplina

- `CMP1071 - Trabalho de Conclusao de Curso I` e a primeira metade do TCC do curso, com `4 creditos` e `80 horas`.
- O TCC completo e desenvolvido em dois periodos letivos: `CMP1071` e `CMP1072`.
- Para matricula em `TCC I`, o estudante deve estar faltando, no maximo, `72 creditos` para integralizar a matriz curricular.
- O tema deve estar alinhado as linhas de pesquisa da Escola Politecnica e de Artes.

### Modalidades e formato tecnico

- O curso aceita tres modalidades: `monografia`, `artigo cientifico` e `produto de software`.
- `Monografia` e `produto de software` devem ser feitos individualmente.
- `Artigo cientifico` pode ser individual ou em dupla.
- Na modalidade `monografia`, o texto deve seguir as normas `ABNT` mais recentes.
- Na modalidade `produto de software`, a documentacao deve seguir o manual especifico da Escola Politecnica e de Artes.
- Na modalidade `artigo`, a formatacao deve seguir o evento ou periodico escolhido; a submissao obrigatoria ocorre em `TCC II`.

### Orientacao, banca e avaliacao

- O trabalho e conduzido sob orientacao de professor da Escola, com titulacao minima de mestre.
- O orientador deve realizar reunioes semanais individuais de `45 minutos`, definir escopo, revisar componentes tecnicos e verificar plagio.
- Pesquisas com participantes humanos, animais ou coleta de dados sensiveis devem passar pelo Comite de Etica em Pesquisa da PUC Goias.
- A apresentacao de `TCC I` e publica e tem duracao de `20 minutos`.
- A banca de `TCC I` deve ser composta pelo orientador e por, no minimo, mais `1 professor`.
- A avaliacao e dividida em `N1` (orientador) e `N2` (banca). A nota da banca considera apresentacao e versao escrita.
- A aprovacao exige media final igual ou superior a `6,0`.

### Escopo tecnico adotado neste repositorio

Inferencia a partir de `main.tex`: este repositorio trata o `TCC I` como um `projeto de pesquisa tecnico` na modalidade de texto academico, e nao como a monografia final de `TCC II`.

O documento atual ja esta organizado com as secoes:

- introducao e contextualizacao do problema;
- problema de pesquisa;
- objetivo geral e objetivos especificos;
- hipotese central;
- contribuicao academica;
- fundamentacao teorica;
- metodologia;
- modelagem do problema;
- desenvolvimento do artefato;
- avaliacao;
- conclusao;
- referencias.

### Recorte tecnico do projeto atual

Pelo conteudo de `main.tex`, o recorte tecnico do TCC I neste projeto e:

- modelar a orquestracao de filas de caminhoes em patios agroindustriais como problema de escalonamento sob restricoes;
- definir variaveis, restricoes operacionais e criterios de decisao;
- descrever um artefato computacional inicial para apoio a decisao;
- comparar o artefato com um baseline operacional, como `FIFO`;
- avaliar o trabalho com metricas como tempo de espera, throughput, makespan e auditabilidade.

### O que este template cobre hoje

- capa e folha de rosto em `LaTeX`;
- estrutura textual inicial para `TCC I`;
- configuracao de pagina `A4`;
- uso de `fontspec`, portanto a compilacao deve ser feita com `XeLaTeX`;
- imagem institucional em `images/puc-goias.png`.

### Fontes oficiais

- PPC de Ciencia da Computacao da PUC Goias (secao `3.10 Trabalho de Conclusao de Curso`, PDF de 30/07/2024): <https://sistemas.pucgoias.edu.br/sistemas/concursos/editais/702024-curso-de-ciencias-da-computacao/1731592827564_ppc-ciencia-da-computacao-puc-goias-30-de-julho-de-2024.pdf>
- Regulamento geral de TCC da PUC Goias: <https://recredenciamento.pucgoias.edu.br/wp-content/uploads/2023/03/Regulamento-TCC_SLN24.pdf>

Se a coordenacao, o orientador ou a Escola Politecnica e de Artes fornecerem um manual mais recente de `TCC I`, ele deve prevalecer sobre este resumo.
