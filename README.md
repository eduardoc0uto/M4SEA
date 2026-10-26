# M4SEA · Floating Structures

MVP local em Python/Streamlit para configuração, validação e análise de modelos OpenFAST, no âmbito da dissertação «Análise e Previsão de Comportamentos em Estruturas Flutuantes com Digital Twins e Sistemas Inteligentes».

## Estado e limites

A aplicação arranca sem baseline. Todos os parâmetros iniciais são `null` e `unknown`; não representam um WindFloat validado. Não são fornecidos modelos, dados de empresa ou executável OpenFAST. A ausência destes inputs impede gerar/executar uma simulação científica. Nenhum diretório histórico Windows é alterado.

As sete páginas são Dashboard, Structure, Environment, Mooring, Run OpenFAST, Results e Calibration. A configuração em memória é aplicada apenas ao submeter os formulários. Guardar cria um JSON novo em `02_Configs/Working`; carregar uma configuração guardada faz-se na sidebar.

## Instalação

Python 3.12 recomendado. No PowerShell, no diretório pretendido (`C:\Users\Administrador\Documents\OpenFAST\M4SEA_FloatingStructures`), coloque os ficheiros deste repositório e execute:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run 08_DigitalTwin/WebApp/app.py
```

Em Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run 08_DigitalTwin/WebApp/app.py --server.address 127.0.0.1
```

Não reutiliza nem altera automaticamente a `.venv` ou a cópia do toolbox do projeto histórico. As dependências estão fixadas e o toolbox referencia um commit específico. A instalação necessita de Git e acesso a PyPI/GitHub. O executável Windows não funciona nativamente em Linux: configure um binário nativo nesse sistema.

## Arquitetura

- `m4sea/config.py`: JSON, paths, estados e snapshots de trabalho.
- `m4sea/validation.py`: regras determinísticas e severidades.
- `m4sea/cases.py`: cópia independente, hashes, execução, logs e diagnóstico.
- `m4sea/openfast.py`: adaptador toolbox para inputs escalares e outputs binários.
- `m4sea/ui*.py`: páginas e editores separados dos serviços.
- `08_DigitalTwin/WebApp/app.py`: entrada Streamlit.
- `01_Models`: baselines; `02_Configs`: configurações e templates.
- `05_Simulations`: Pending, Running, Completed, Failed e Archive.
- `06_Data/Raw` e `13_Sources`: dados originais e fontes, separados de resultados processados.
- `09_IntelligentSystems/Calibration`: fronteiras reservadas para extensões futuras.
- `14_Tests`: testes do domínio, integração toolbox e navegação Streamlit.

Os diretórios vazios são criados quando necessários; Git não preserva diretórios vazios. Não há otimização, LLM, ML ou modelos físicos de bombas, baterias e corrosão. Templates futuros não contêm valores assumidos.

## Configuração e workflow

1. Disponibilize uma **cópia autocontida** dos inputs OpenFAST em `01_Models/WindFloat_Research`, mantendo o projeto histórico intacto. Para outra estrutura, crie um diretório em `02_Configs` com os três JSONs e um baseline correspondente em `01_Models`.
2. Na página Run OpenFAST, configure baseline, caminho relativo do `.fst` principal e executável. O caminho Windows indicado no pedido é apenas uma sugestão de configuração, não foi verificado nesta máquina Linux.
3. Structure e Environment mostram valor, unidade, estado, fonte, descrição e situação da escrita OpenFAST. Preencha os campos conhecidos, sem atribuir confirmação automática. Massa e profundidade são obrigatórias nesta versão.
4. Configure mappings escalares após conferir ficheiros, campos e unidades do seu modelo. Exemplo de formato (não é calibração científica):

```json
{
  "structure.platform_mass": {"file": "ElastoDyn.dat", "field": "PtfmMass"},
  "environment.water_depth": {"file": "SeaState.dat", "field": "WtrDpth"}
}
```

Os nomes e a localização variam com a versão do OpenFAST. Só parâmetros com mapping são escritos, usando `FASTInputFile`; os restantes são **apenas armazenados**. As unidades não são convertidas automaticamente. Não existem mappings de tabelas MoorDyn nesta versão.

5. Em Mooring, edite uma lista JSON com número variável de linhas. Use `02_Configs/Templates/mooring_line.json`; `anchor.value` e `fairlead.value` são vetores `[x,y,z]`. Convenção: Z positivo para cima e seabed em `-water_depth`, tolerância geométrica 0,1 m. Não preencha coordenadas desconhecidas com zeros. Cada propriedade contém metadados de origem/estado.
6. Execute Validate Configuration. ERROR bloqueia geração/execução; WARNING permite continuar mediante reconhecimento explícito. Confira especialmente os parâmetros apenas armazenados.
7. Save Working Configuration preserva um snapshot fora do baseline. Generate Case copia o baseline para um ID único, escreve alterações apenas na cópia, guarda configuração e hashes. Inputs referenciados devem estar dentro da cópia; symlinks e referências externas conhecidas são recusados. Outputs `.outb` antigos copiados são removidos **apenas do caso**, para não serem confundidos com novos resultados.
8. Run OpenFAST executa em segundo plano, com feedback periódico e logs. O timeout é de uma hora. Um caso alterado depois de gerado é recusado. Cada caso só deve ser executado uma vez; gere um novo para repetir.
9. Sucesso exige código de saída zero, ausência de erro fatal/NaN reconhecido e output `.outb` legível. Guarda `stdout.log`, diagnósticos, métricas e metadata, e classifica em Completed/Failed. Mensagens de diagnóstico são hipóteses, não provas causais.
10. Results lê canais reais do output, apresenta séries e min/max/média/desvio padrão amostral e compara até dois outputs. Calibration regista manualmente alvo, métrica, diferença, limites e caso associado; não calcula períodos próprios nem sugere ajustes físicos.

O leitor preventivo de referências cobre caminhos entre aspas com extensões comuns em `.fst`/`.dat`; não é um parser completo de todos os módulos OpenFAST, WAMIT ou controladores. O próprio OpenFAST faz a validação final dos seus inputs. Use baselines autocontidos e confiáveis. O runner é local, sem isolamento para executáveis não confiáveis. Reiniciar Streamlit durante uma execução não oferece recuperação automática; casos em Running devem ser inspecionados antes de nova execução. O log em tempo real depende do buffering do executável. A UI mantém um caso atual por sessão; os resultados anteriores continuam disponíveis em Results.

## Validação do desenvolvimento

```bash
.venv/bin/python -m pytest -q 14_Tests
```

No Windows substitua `.venv/bin/python` por `.venv\Scripts\python.exe`. Os testes de subprocesso usam um runner sintético POSIX e não são uma simulação científica; os testes de domínio e UI são independentes do OpenFAST. O teste binário cria um `.outb` sintético pelo toolbox e verifica leitura e métricas. Uma validação científica real requer o baseline e binário do utilizador e deve conferir canais, unidades e comportamento físico.
