# Âncora exploratória RHFS

`rhfs_method_performance_matrix.csv` é uma cópia byte a byte da matriz local
`../agro_yard_dfjsp_paper/catalog/method_performance_matrix.csv`. A origem, o
commit e os hashes SHA-256 constam de `rhfs_matrix_provenance.json`. A cópia
tem 513 linhas de dados; o filtro do script produz 99 diferenças pareadas,
agrupando três contrastes RHFS em uma única população de ruído centrado.

O script `scripts/power_analysis_rhfs.py` explora a rejeição de **um teste de
Wilcoxon unilateral**, com deslocamentos hipotéticos sobre esse ruído. Não
estima a potência da decisão completa de H1: não simula a conjunção dos três
comparadores, a não inferioridade de throughput, o teste deslocado no limiar
de ganho de 15%, nem Holm entre estratos. A reamostragem desse pool também
não preserva a dependência entre contrastes oriundos da mesma instância.
Trata-se de uma âncora auxiliar de variabilidade, não de observações do TCC II.

`power_analysis_rhfs_summary.csv` e `power_curve_reference.csv` foram
preservados sem alteração e **não foram regenerados nesta revisão**. O
sidecar `power_analysis_rhfs_historical_metadata.json` identifica seus hashes,
os parâmetros presentes nos CSVs e a ausência do recibo da execução original.
A origem exata usada naquela execução não está comprovada. O rótulo legado
`point_type=H1` significa apenas o deslocamento hipotético de 15% do teste
isolado; o valor 1,0 nessa linha não demonstra potência de H1.

Uma nova execução deliberada precisa de destino sem os três arquivos de
saída existentes; o script não sobrescreve os CSVs históricos. Por exemplo,
na raiz do repositório, com o ambiente deliberadamente instalado:

```text
rtk proxy experimento-notebook\.venv\Scripts\python.exe scripts/power_analysis_rhfs.py --output-dir data/power_rhfs_new --replicates 5000 --seed 20260531 --alpha 0.05
```

Esse comando não foi executado nesta revisão. Uma execução concluída gera
`power_analysis_rhfs_metadata.json` com hashes da entrada, do script e dos
dois CSVs, parâmetros, versões e escopo exploratório. A cópia local da matriz
é a entrada padrão, independente do diretório de execução. As novas curvas
usam `15pct_hypothetical` no lugar do rótulo ambíguo `H1`.

Separadamente, os intervalos bootstrap do módulo `statistics.py` usam 5.000
reamostragens pareadas, conforme o protocolo; cada comparação serializa
`bootstrap_iterations=5000` ao lado da semente e do intervalo observado.
