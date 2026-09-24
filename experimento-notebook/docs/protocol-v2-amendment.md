# Emenda prospectiva — protocolo 2.0.0

Decisão autoral de 24 de setembro de 2026, registrada antes da geração do dataset
e das campanhas científicas desta versão. O autor confirmou que a validação de
face não foi realizada e autorizou uma avaliação computacional sem revisores
humanos obrigatórios, com parâmetros como hipóteses de engenharia e A2 restrito
à rastreabilidade automatizada. Esta emenda e seu commit constituem registro
prospectivo local; não se alega pré-registro público ou aprovação da banca.

## Escopo e critérios substituídos

O desenho é um estudo computacional comparativo com dados sintéticos. Parâmetros
têm origem, unidades, faixas e limitações documentadas, sem calibração empírica
ou aprovação externa demonstrada. H1 é confirmatória somente dentro do modelo
sintético especificado; não estabelece eficácia numa cooperativa real.

- Face e avaliação humana de A2: `NOT_EVALUATED`, fora dos requisitos da v2.
  A ausência de avaliação nunca recebe `APPROVED` ou `complete`.
- A1: ausência de violações das restrições modeladas, verificada por auditor
  independente. Não é certificação de segurança operacional real.
- A2: completude, proveniência e reconstruibilidade automatizada de 100% dos
  logs, incluindo cinco campos de justificativa, candidatos, exclusões,
  comandos e quebra de FIFO. Não mede legibilidade, confiança ou usabilidade.
- Operador: `synthetic_auto_accept` na matriz científica. Ensaios sintéticos
  de rejeição/override continuam verificações técnicas externas ao notebook.
- Unreal: cena, importador JSONL e replay continuam no escopo, verificados
  tecnicamente contra o log canônico. Avaliação com pessoas fica como trabalho
  futuro. Auditoria aprovada sozinha não conclui essa entrega nem o TCC.

Esta emenda substitui os requisitos humanos de execução/aceitação da
especificação de 2026-09-02, sobretudo face e seção 9.2. Revisão amostral e κ
ficam como referência para pesquisa futura, não como requisitos da v2.
Demais contratos técnicos continuam vigentes.

## Elementos preservados

H1 e seus limiares, desfechos, IUT/Holm, métricas secundárias, 72 cenários,
sementes 101–150, cinco políticas principais, regra CRN, horizonte, controles
base, estratos, 5.000 reamostragens bootstrap, capacidade/TTL, auditoria,
rejeição estrutural, freeze e hashes permanecem inalterados. Não há seleção de
sementes ou calibração de políticas por desempenho observado.

O fluxo integral tem 810.150 execuções de política/dia:

| Fase | Grade | Execuções |
| --- | --- | ---: |
| Piloto | 15 cenários × 50 sementes × 5 políticas | 3.750 |
| Principal | 72 × 50 × 5 | 18.000 |
| Estresse posterior | 54 controles × 72 × 50 × 4 políticas | 777.600 |
| Políticas exploratórias | 72 × 50 × 3 políticas | 10.800 |

O piloto relata IQR e IC95% do ganho pareado sem recalibrar parâmetros.
Estresse e políticas exploratórias usam namespaces próprios, fora de H1.
A regra de robustez conjunta de 75% mantém-se na seção 10 da especificação.
`H1=NOT_SUPPORTED` é resultado admissível de pesquisa concluída; pacote
incompleto é falha, nunca evidência contra ou a favor de H1.

## Identidades e execução

`config/confirmatory.json` identifica v2; a configuração v1 permanece em
`config/archive/confirmatory.v1.json`. A mudança altera o hash da configuração
e exige datasets/runs novos. O recibo real de face permanece em `PENDING` no
arquivo original como histórico. Artefatos de engenharia não são promovidos
a resultados v2. Não foram consultados resultados científicos v2 antes desta
emenda. Não se aplica checklist biomédico de relato a este desenho.

O manifesto identifica `study_scope`, avaliação humana `not_evaluated` e
aceitação global `pending` enquanto outras entregas não forem demonstradas.
A geração v2 aceita explicitamente ausência de recibo de face; v1 conserva
sua exigência. Não existe chave genérica de bypass.

Falhas preservam configuração, logs, namespaces e causas. Reamostragem
estrutural permanece ação explícita e rastreável anterior à observação dos
ganhos. O notebook não inclui testes, smokes ou fallback reduzido.

Por solicitação explícita do autor, a operação padrão do notebook passa a ser
a campanha integral, substituindo o percurso reduzido das seções 3 e 11 da
especificação anterior. Isso não relaxa gates nem autoriza repetir células
falhadas. O limite operacional do executor é sete dias por célula.

Na documentação das identidades, esclarece-se a semântica já implementada e
verificada: `controlled_view_hash` identifica o controle completo;
`event_overlay_hash` identifica os eventos exógenos e pode repetir quando
apenas H0, buffer ou limiar mudam. Preservam-se as funções e seus hashes;
ambos são conferidos contra a projeção rederivada, por instância e controle.
