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
