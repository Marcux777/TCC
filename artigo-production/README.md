# Artigo para a revista Production

Pasta de preparação editorial do PequiFlux. O manuscrito de trabalho está em
[manuscript.md](manuscript.md). Os arquivos da revista estão em
[`originais/`](originais/). O texto e o protocolo científicos continuam tendo
como fonte canônica [`../main.tex`](../main.tex); a bibliografia canônica é
[`../refs.bib`](../refs.bib). Esta pasta não altera o TCC nem antecipa resultados.

## Contrato editorial consultado em 22 de setembro de 2026

Fontes oficiais: [Guidelines and Policies](https://prod.org.br/instructions) e
[About the Journal](https://prod.org.br/about). Consultar as páginas atuais
antes da submissão.

| Item | Exigência verificada |
| --- | --- |
| Enquadramento | Artigo original com resultados inéditos em operações/engenharia de produção. A revista não aceita relatório técnico, comunicação breve ou revisão narrativa simples. |
| Idioma e extensão | Inglês; 4.000–8.000 palavras incluindo referências. |
| Estrutura | Abstract, Keywords, Introduction, Methods, Results, Discussions, Conclusions, References. Seções e subseções numeradas desde a Introduction. |
| Título e resumo | Título com até 15 palavras. Abstract estruturado em *Paper aims*, *Originality*, *Research method*, *Main findings* e *Implications for theory and practice*, com até 250 palavras. Três a cinco keywords sem repetir termos do título. |
| Arquivo de avaliação | Word `.docx` ou LaTeX, A4, margens de 2,5 cm, Times New Roman 12 no texto, espaçamento 1,5, uma coluna, até 3 MB. Arquivo cego, sem autores/afiliações ou marcas identificadoras. |
| Citações | APA autor–data; cada citação precisa corresponder a uma referência. Figuras e tabelas inseridas após a primeira chamada no texto. |
| Submissão | Manuscrito, cover letter, formulário de ciência aberta, declaração de conflitos assinada por todos os autores e acordo de autoria/licença assinado pelo correspondente. A política também prevê documentos de ética quando aplicáveis. |
| IA | Declaração específica antes das referências sobre o uso de IA/LLM na elaboração do texto. |
| Política relevante | A revista declara não aceitar contribuições previamente publicadas como preprints. Revisão duplo-cega. Sem taxa de submissão ou publicação segundo a página consultada. |

O modelo DOCX contém texto instrutivo e exemplos que **não pertencem ao artigo**.
Ele fica intacto em `originais/`. Os formulários estão em branco e não foram
assinados. Antes de entregar ou submeter, confrontar a versão atual das normas
e preencher os documentos apenas com informações confirmadas pelos autores.

## Arquivos oficiais baixados

| Arquivo | Fonte oficial | SHA-256 |
| --- | --- | --- |
| `originais/production_template_1.0.docx` | [Modelo de manuscrito](https://s3.amazonaws.com/host-client-assets/files/production/production_template_1.0.docx) | `7EA26B0FBAFE828E1E77D7A14C2DB161EF1DF8844FA40BCDEE10A2A234254F9D` |
| `originais/Open-Science-Compliance-Form_en.docx` | [Formulário de ciência aberta](https://s3.amazonaws.com/host-client-assets/files/production/Open-Science-Compliance-Form_en.docx) | `E658F217DBC23085BA0F6397048B5EA9324ECAEEB8011B9D53F712666C0AF271` |
| `originais/Conflict-of-Interest-Statement.docx` | [Declaração de conflitos](https://docs.google.com/document/d/1FqSyaRh6zO7YdsPfK0OGApjSxiHyBGaIE5Jjqym5zxA/export?format=docx) | `0EA8E628B747FBB4FBFB68B013ED7C678B46C20D0AFD721ADABEFCAC97629D26` |
| `originais/Form_Copyright_Agreement.docx` | [Acordo de autoria/licença](https://docs.google.com/document/d/1bMHevIxUiUFshx8RhJMF_zi2qF7-dF9D/export?format=docx) | `4E2A9BB7438C0FF16AC11B82DD4E0CC7ED6B66C4A2B620F685263EC6AF813675` |

## Encadeamento da redação

1. **Problema e contribuição:** adaptar a pergunta e o recorte de despacho online
   de `main.tex`, Introdução (linhas 272–323). Posicionar o trabalho para decisões
   operacionais em recebimento agroindustrial, sem chamá-lo de gêmeo digital.
2. **Literatura:** condensar `main.tex`, Referencial Teórico (linhas 328–514), em
   poucos eixos: recebimento de grãos, agendamento/despacho de caminhões,
   replanejamento sob incerteza e rastreabilidade. Selecionar apenas referências
   realmente citadas em `../refs.bib`; conferir metadados e suporte de cada claim.
3. **Método:** derivar formulação e arquitetura de `main.tex` (linhas 515–1012)
   e cenários, políticas, métricas e inferência (linhas 1013–1310). Preservar a
   separação entre DES, política de despacho, auditoria e visualização Unreal.
4. **Resultados:** preencher exclusivamente a partir da campanha confirmatória
   auditada e das exportações em `../experimento-notebook/results/`. Fontes
   previstas: `tables/table_h1.csv`, `table_throughput.csv`, `table_metrics.csv`,
   `table_audit.csv`, `table_a2.csv` e figuras. São caminhos previstos pelo
   protocolo, não resultados existentes. Relatar estratos separadamente.
5. **Discussão e conclusões:** confrontar os resultados observados com a
   hipótese H1, os critérios A1/A2 e as ameaças de validade em `main.tex`
   (linhas 1417–1453). Não extrapolar dos cenários sintéticos a um pátio real.
6. **Pacote editorial:** após fechar evidências e revisão autoral, converter o
   manuscrito para o modelo oficial, conferir limite de palavras e anonimização,
   escrever a cover letter com os resultados reais e completar os formulários.

## Pendências que controlam afirmações

- A validação humana de face dos cenários está pendente no
  [`face_validation_receipt.json`](../experimento-notebook/inputs/face_validation_receipt.json).
- A matriz confirmatória de 18.000 execuções, a auditoria completa A1/A2 e a
  análise de H1 não estão disponíveis no estado documentado em
  [`governance-status.md`](../experimento-notebook/docs/governance-status.md).
- O replay tridimensional em Unreal ainda não foi entregue; o artigo pode
  concentrar-se no DES e no despacho sem prometer essa visualização como achado.
- A avaliação humana de legibilidade e intervenção pertence a A2 e não pode
  ser substituída por logs completos ou por aceitação sintética automática.
- Autoria, contribuições CRediT, financiamento, conflitos, ética e licença
  precisam de decisão e confirmação dos autores antes de submissão.

O rascunho em `manuscript.md` usa chaves de citação de `../refs.bib` como
marcadores de trabalho. Antes da versão de avaliação, verificar cada fonte
original e converter as citações e referências para APA.
