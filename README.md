# TCC PequiFlux

Fonte canônica do Trabalho de Conclusão de Curso sobre despacho online de
caminhões em pátios agroindustriais. Este repositório define a terminologia, o
protocolo experimental, os parâmetros, as tabelas e os limites das conclusões.
Uma implementação ou cópia mantida em outro repositório não substitui o texto
canônico daqui.

## Fontes normativas do projeto

- `main.tex`: texto e protocolo canônicos.
- `refs.bib`: bibliografia canônica.
- `images/` e `data/`: figuras e dados auxiliares usados pelo texto.
- `latexmkrc`: configuração de compilação.

O arquivo histórico `projeto-tcc.tex` foi removido porque descrevia uma versão
antiga do protocolo e criava uma segunda fonte de verdade.

## Classificação correta do artefato visual

O projeto produzirá um **modelo digital**, e não um gêmeo digital.

- O simulador Python de eventos discretos é a camada experimental e produz
  estados, decisões, logs e métricas.
- O Unreal Engine 5.8 será a camada tridimensional de visualização e replay,
  alimentada por eventos JSONL versionados exportados pelo simulador.
- O Unreal não recalcula H1, A1 ou A2 e não altera resultados experimentais.
- Não existe atualmente um pátio físico individual pareado, telemetria contínua
  nem sincronização bidirecional em tempo real. Sem esses elementos, a
  classificação “gêmeo digital” seria tecnicamente indevida.

O projeto Unreal já está inicializado em `../UnrealProject`, associado ao Unreal
Engine 5.8. A cena de domínio, os ativos, o importador JSONL e os controles de
replay ainda precisam ser implementados.

## Arquitetura dos artefatos

```text
TCC canônico (este repositório)
        |
        +-- protocolo e parâmetros --> ../agro-yard-des-experiment
        |                                 |
        |                                 +-- logs/eventos JSONL
        |                                             |
        +---------------------------------------------v
                                          ../UnrealProject
                                          modelo digital 3D
```

O repositório `../agro-yard-des-experiment` contém o motor DES e os comparadores.
Snapshots do texto mantidos nele devem ser gerados mecanicamente a partir deste
repositório e tratados como somente leitura.

## Estado atual

Concluído ou especificado:

- formulação do despacho online e das restrições rígidas;
- plano fatorial, sementes, comparadores, métricas e decisão estatística;
- parâmetros antes implícitos agora congelados no TCC;
- distinção conceitual entre modelo digital e gêmeo digital;
- arquitetura de integração DES → JSONL → Unreal Engine 5.8;
- implementação preliminar do simulador e testes automatizados no repositório
  adjacente.

Ainda necessário no TCC II:

- realizar e documentar a validação de face com orientadora/especialista;
- aplicar o auditor independente A1/A2 à matriz completa e concluir a auditoria humana de A2;
- executar a matriz confirmatória completa e analisar H1;
- construir a cena e os ativos do pátio no Unreal Engine 5.8;
- implementar, validar e demonstrar o replay de eventos JSONL;
- substituir resultados previstos por resultados observados;
- congelar e publicar o pacote final com URL, tag ou hash de commit.

## Compilação

O documento usa `fontspec` e deve ser compilado com XeLaTeX:

```bash
latexmk -xelatex main.tex
```

O PDF principal é gerado em `build/main.pdf` e copiado para `main.pdf` pela
configuração do projeto.

## Enquadramento acadêmico

O trabalho está enquadrado como TCC I de Ciência da Computação da PUC Goiás. O
TCC I consolida a modelagem e o protocolo; a execução confirmatória e a
finalização do modelo digital pertencem ao TCC II. Regras institucionais e
orientações formais mais recentes da coordenação prevalecem sobre este resumo.

Fontes institucionais consultadas:

- [PPC de Ciência da Computação da PUC Goiás](https://sistemas.pucgoias.edu.br/sistemas/concursos/editais/702024-curso-de-ciencias-da-computacao/1731592827564_ppc-ciencia-da-computacao-puc-goias-30-de-julho-de-2024.pdf)
- [Regulamento geral de TCC da PUC Goiás](https://recredenciamento.pucgoias.edu.br/wp-content/uploads/2023/03/Regulamento-TCC_SLN24.pdf)
