# Template e Guia de Submissão: Revista Production (ABEPRO / SciELO)

Este diretório (`production/`) reúne todos os arquivos e modelos necessários para submissão do artigo na revista **Production** (Associação Brasileira de Engenharia de Produção - ABEPRO), indexada no SciELO, Scopus e Web of Science.

---

## 1. Regras Editoriais Oficiais da Revista *Production*

- **Portal de Submissão**: [ScholarOne - Production SciELO](https://mc04.manuscriptcentral.com/prod-scielo)
- **Idioma Obrigatório**: Inglês.
- **Tamanho do Manuscrito**: Entre **4.000 e 8.000 palavras** (incluindo referências). O presente manuscrito possui aproximadamente 5.100 palavras, enquadrando-se perfeitamente na faixa permitida.
- **Formato da Página**: Papel A4, margens de 2,5 cm em todos os lados.
- **Tipografia**: Times New Roman, corpo 12 para o texto principal, corpo 10 para tabelas e figuras.
- **Espaçamento**: 1,5 entrelinhas, texto justificado.
- **Estrutura do Resumo (Abstract)**: Máximo de 250 palavras, estruturado obrigatoriamente nos 5 tópicos:
  1. *Paper aims*
  2. *Originality*
  3. *Research method*
  4. *Main findings*
  5. *Implications for theory and practice*
- **Palavras-chave (Keywords)**: De 3 a 5 termos separados por ponto e vírgula, sem repetir termos que já estejam no título do artigo.
- **Avaliação por Pares às Cegas (Double-Blind Review)**:
  - O **Main Document** (manuscrito principal) deve ser estritamente anônimo, sem identificação de autores, e-mails, universidades, órgãos de fomento ou agradecimentos.
  - A identificação completa dos autores é enviada em arquivo separado: a **Title Page**.

---

## 2. Inventário de Arquivos do Pacote de Submissão

| Arquivo | Tipo no ScholarOne | Descrição |
| :--- | :--- | :--- |
| `manuscript_anonymous.tex` / `.pdf` | **Main Document** | Manuscrito completo em inglês, anônimo para avaliação duplo-cega, com resumo estruturado, figuras TikZ e tabela de resultados. |
| `title_page.tex` / `.pdf` | **Title Page** | Página de título com nomes completos, afiliações institucionais, ORCIDs, autor correspondente, agradecimentos e financiamento. |
| `cover_letter.tex` / `.pdf` | **Cover Letter** | Carta de apresentação formal ao Editor-Chefe justificando o enquadramento em *Logistics 5.0 in Production Engineering*. |
| `conflict_of_interest.tex` / `.pdf` | **Declaration of Conflict of Interest** | Declaração assinada de ausência de conflitos de interesse. |
| `Open-Science-Compliance-Form_en.docx` | **Open Science Compliance Form** | Formulário padrão oficial da SciELO em formato DOCX baixado diretamente do repositório da SciELO. |
| `refs.bib` | **Supplementary** | Base bibliográfica completa utilizada pelo Biber/BibLaTeX. |
| `latexmkrc` | **Configuração** | Script de compilação isolada para compilar os documentos para a pasta `build/`. |

---

## 3. Instruções de Compilação dos Documentos

Para compilar todos os documentos do pacote utilizando o `latexmk`:

```bash
cd production

# 1. Compilar o manuscrito anônimo principal
latexmk -xelatex manuscript_anonymous.tex

# 2. Compilar a Title Page
latexmk -xelatex title_page.tex

# 3. Compilar a Cover Letter
latexmk -xelatex cover_letter.tex

# 4. Compilar a declaração de conflito de interesses
latexmk -xelatex conflict_of_interest.tex
```

Os PDFs gerados estarão prontos para submissão imediata na pasta `production/` e em `production/build/`.

---

## 4. Passo a Passo para Submissão no ScholarOne

1. Acesse o sistema [ScholarOne da revista Production](https://mc04.manuscriptcentral.com/prod-scielo) e faça login como autor.
2. Clique em **“Start New Submission”** -> **“Begin Submission”**.
3. **Step 1 - Type, Title, & Abstract**:
   - Selecione o tipo: *Original Research Article*.
   - Cole o título e o resumo estruturado (conforme redigido em `manuscript_anonymous.tex`).
4. **Step 2 - File Upload**:
   - Faça upload de `manuscript_anonymous.pdf` como **Main Document**.
   - Faça upload de `title_page.pdf` como **Title Page**.
   - Faça upload de `cover_letter.pdf` como **Cover Letter**.
   - Faça upload de `conflict_of_interest.pdf` como **Declaration of Conflict of Interest**.
   - Faça upload de `Open-Science-Compliance-Form_en.docx` preenchido como **Open Science Compliance Form**.
5. **Step 3 - Attributes / Keywords**:
   - Insira as 5 palavras-chave: *Discrete-event simulation; Reentrant hybrid flow shop; Bulk terminals; Operational resilience; Decision support systems.*
6. **Step 4 - Authors & Institutions**:
   - Adicione os autores (Marcus Vinicius Santos da Silva e Profa. Dra. Maria José Dantas), afiliações e ORCIDs.
7. **Step 5 - Review & Submit**:
   - Verifique a prova gerada em PDF pelo sistema, confirme que o documento principal não possui identificação de autoria e submeta.
