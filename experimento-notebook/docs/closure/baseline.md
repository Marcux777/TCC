# Baseline de fechamento — Tarefa 1

Rodada executada em 7 de setembro de 2026, com instalação limpa, kernel
correspondente e execução única da suíte existente. Os números abaixo foram
observados nesta rodada; resultados históricos não são usados como baseline atual.

## Estado anterior à branch

Captura realizada às 23:05:56 UTC (20:05:56 em Brasília), antes da criação de
`codex/tcc-python-baseline`:

```text
git rev-parse HEAD
652bee7fb0ae56b012b3261e2ad249b506dbd163

git status --short
(saída vazia)
```

`git diff --binary`, `git diff --cached --binary` e
`git ls-files --others --exclude-standard` também produziram saída vazia.
A branch inicial era `main`, 11 commits à frente de `origin/main`, com um único
worktree em `C:\p\PequiFlux\TCC`. Nenhum arquivo local foi apagado ou sobrescrito.
O status não enumera arquivos ignorados: a `.venv` preexistente e os artefatos
locais anteriores foram preservados.

## Interpretador e instalação limpa

O contrato deste fechamento é `requires-python = ">=3.13,<3.14"`, com ambiente
suportado CPython 3.13.x em Windows x64. A versão efetivamente verificada nesta
rodada é **3.13.3**, em Windows 11 build 26200. Python 3.11 não é suportado;
3.12 e 3.14 não foram testados nesta rodada. O lock conservou todos os pins;
somente recebeu comentários que identificam o contrato e este registro.

O executável instalado foi confirmado antes de criar o ambiente:
`C:\Users\marcu\AppData\Local\Programs\Python\Python313\python.exe`.
Uma verificação confirmou que `C:\p\PequiFlux\TCC\tmp\closure-baseline\venv`
não existia. O novo ambiente tem `include-system-site-packages = false` e
continha somente `pip==25.0.1` antes da instalação.

A instalação de `requirements.lock`, incluindo o pacote local `-e .`, terminou
com código 0. `pip check` retornou código 0 e `No broken requirements found.`.
Não houve falha de instalação ou alteração de pins para contornar dependências.
A etapa de instalação levou 84,0692 s. Foram conferidos os 64 pins do lock,
além da instalação editável de `pequiflux-experiment==0.1.0`.

| Componente | Versão observada |
| --- | --- |
| CPython / pip | 3.13.3 / 25.0.1 |
| NumPy / SciPy | 2.5.2 / 1.18.1 |
| pandas / PyArrow | 3.0.5 / 25.0.1 |
| Matplotlib / pytest | 3.11.1 / 9.1.1 |
| nbformat / nbclient / nbconvert | 5.11.1 / 0.11.0 / 7.17.1 |
| ipykernel / jupyter_client | 7.3.0 / 8.10.0 |

SHA-256 de `requirements.lock` usado nesta rodada:
`f8638a96c72a98ade43de388f4b80f1ea3ff456945b4558674ea71713af67b16`.

## Kernel

O kernel `python3` foi registrado com `--sys-prefix` no ambiente novo. A busca
padrão do Jupyter resolveu seu `argv[0]` para:

```text
C:\p\PequiFlux\TCC\tmp\closure-baseline\venv\Scripts\python.exe
```

O kernel foi iniciado, importou NumPy, SciPy, ipykernel e o pacote local, e
retornou o mesmo `sys.executable`. A validação também conferiu cada pin instalado
e sua declaração `Requires-Python`. O kernel de verificação foi encerrado após
a coleta. Nenhum kernelspec global ou ambiente anterior foi substituído.

## Execução atual

A instalação e o kernel foram verificados antes de iniciar `python -m pytest -q`
em `experimento-notebook/`. A suíte completa foi executada **uma vez**, sem
filtros, exclusões, retry ou nova suíte permanente, entre 23:09:06 e 23:34:23 UTC
(20:09:06–20:34:23 em Brasília).

| Verificação | Resultado observado |
| --- | --- |
| Instalação do lock em ambiente novo | Código 0; 64 pins conferidos e pacote editável instalado |
| `pip check` | Código 0; nenhuma dependência quebrada |
| Kernel `python3` | Código 0; executável e imports confirmados no kernel em execução |
| `python -m pytest -q` | **295 passed, 1 warning in 1516.55s (0:25:16)**; código 0; nenhuma falha ou skip |
| `python -m compileall -q src` | Código 0, sem saída de erro; executado após a suíte |

O aviso do pytest é um `RuntimeWarning` do PyZMQ sobre a ausência de
`add_reader` no event loop Proactor do Windows, durante o teste de execução
do notebook. O teste passou e o aviso foi preservado integralmente. O stderr
da verificação separada do kernel também conserva o aviso emitido pelo
ipykernel sobre transporte TCP sem criptografia; ele não é erro de instalação.
Não houve alteração de configuração de segurança nem supressão de avisos.

O baseline é de engenharia. Testes com fixtures não aprovam validação humana
de face, A2 humano, geração principal ou resultados científicos.

## Comandos e isolamento

Comandos equivalentes aos argumentos registrados nas receitas, em PowerShell
e a partir do pacote. O diretório de destino estava ausente na execução abaixo;
para outra instalação limpa, escolha um novo diretório se ele já existir.

```powershell
cd C:\p\PequiFlux\TCC\experimento-notebook
rtk proxy py -3.13 --version
rtk proxy py -3.13 -m venv ..\tmp\closure-baseline\venv
rtk proxy ..\tmp\closure-baseline\venv\Scripts\python.exe -m pip install -r requirements.lock
rtk proxy ..\tmp\closure-baseline\venv\Scripts\python.exe -m pip check
rtk proxy ..\tmp\closure-baseline\venv\Scripts\python.exe -m pip freeze --all
rtk proxy ..\tmp\closure-baseline\venv\Scripts\python.exe -m ipykernel install --sys-prefix --name python3 --display-name "PequiFlux baseline (Python 3.13)"
rtk proxy ..\tmp\closure-baseline\venv\Scripts\python.exe -m jupyter kernelspec list --json
rtk proxy ..\tmp\closure-baseline\venv\Scripts\python.exe -m pytest -q
rtk proxy ..\tmp\closure-baseline\venv\Scripts\python.exe -m compileall -q src
```

O executor de receitas preserva stdout e stderr integrais, código de saída,
horários e hashes, sem reduzir a saída do pytest. Nenhum novo teste permanente
foi criado. O ambiente e seus logs locais foram mantidos após as verificações.

## Evidência preservada

As cópias integrais foram arquivadas em `evidence/` ao término da rodada. Cada
grupo contém a receita executada, seu recibo e os dois fluxos de saída. Os
recibos conservam os caminhos absolutos originais em `tmp/closure-baseline/runs/`;
as cópias relativas abaixo permitem consultar a evidência pelo repositório.

| Grupo | Registro |
| --- | --- |
| Estado anterior à branch | [HEAD, status e diferenças](evidence/before-branch/receipt.json) |
| Ambiente realmente novo | [Criação e verificação de ausência](evidence/create-environment/receipt.json) |
| Instalação e dependências | [Recibo](evidence/install/receipt.json), [log integral do pip](evidence/install/logs/install-lock.stdout.log), [pip check](evidence/install/logs/pip-check.stdout.log), [todas as versões](evidence/install/logs/installed-versions.stdout.log) |
| Kernel e compatibilidade | [Recibo](evidence/kernel/receipt.json), [ambiente e hashes das entradas](evidence/kernel/artifacts/environment.json), [verificador utilizado](evidence/verify_environment.py.txt) |
| Suíte completa, uma vez | [Recibo](evidence/suite/receipt.json), [stdout integral](evidence/suite/logs/pytest-full-once.stdout.log), [stderr integral](evidence/suite/logs/pytest-full-once.stderr.log) |
| Compilação Python | [Recibo](evidence/compileall/receipt.json) |
| Integridade do arquivo de evidências | [Índice de caminhos, tamanhos e SHA-256](evidence/index.json) |

O código científico, os testes e o notebook correspondem ao HEAD inicial.
Os ajustes desta tarefa abrangem metadados de suporte, comentários do lock e
documentação. O registro do ambiente identifica os hashes dos arquivos de
`src/`, `tests/`, notebook, `pyproject.toml` e lock usados na verificação; todos
foram reconferidos sem mudança após a suíte. Atributos Git locais a `evidence/`
desativam conversão de texto, preservando os bytes e hashes dos logs no commit.
Na inspeção de whitespace do diff, `cr-at-eol` reconhece o CRLF original dos
logs Windows como quebra de linha; os bytes da evidência não foram normalizados.
