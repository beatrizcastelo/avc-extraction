# AVC-Extraction — Extracção Automática de Dados Clínicos

Sistema de extracção automática de informação clínica estruturada a partir de notas médicas em texto livre, no contexto do AVC isquémico.

Desenvolvido no âmbito da dissertação de Mestrado em Inteligência Artificial e Ciência de Dados — FCTUC / ULS Coimbra.

**Autora:** Beatriz Castelo  
**Orientador:** Prof. Pedro Furtado  

---

## O que o sistema faz

Lê qualquer nota clínica de AVC isquémico em texto livre — carta de alta, nota de admissão, consulta de seguimento — e extrai automaticamente:

- **Timestamps** — hora de sintomas, admissão, TC, fibrinólise, punção femoral, recanalização
- **Métricas temporais** — Door-to-Needle, Door-to-Imaging, Door-to-Puncture, Onset-to-Door, etc.
- **Escalas clínicas** — NIHSS admissão/alta, mRS prévio/alta/3 meses
- **Variáveis categóricas** — tipo de episódio, etiologia TOAST, tratamento, território vascular
- **Mortalidade** — vivo aos 30 dias, dias até óbito, causa de óbito

Todo o processamento corre **localmente**, sem enviar dados para fora da máquina — compatível com requisitos RGPD em contexto hospitalar.

---

## Estrutura do Projecto

```
avc-extraction/
│
├── streamlit/                  # Aplicação principal
│   ├── agents/                 # Agentes de extracção (LLM)
│   │   ├── extractor.py        # Agente 1 — timestamps
│   │   ├── metrics.py          # Agente 2 — métricas temporais (Python puro, sem LLM)
│   │   ├── scales.py           # Agente 3 — escalas NIHSS + mRS
│   │   └── categorical.py      # Agente 4 — variáveis categóricas + mortalidade
│   ├── prompts/                # Prompts para cada agente
│   │   ├── timestamps_v2.txt
│   │   ├── scales_nihss.txt
│   │   ├── scales_mrs.txt
│   │   ├── categorical.txt
│   │   └── mortality.txt
│   ├── outputs/                # JSONs gerados por episódio (criado automaticamente)
│   ├── app.py                  # Dashboard Streamlit
│   └── main.py                 # Pipeline principal
│
├── validate_all.py             # Validação automática com ground truth
├── fix_ground_truth_bridging.py# Utilitário de correcção de métricas
│
├── .env.example                # Exemplo de configuração (copiar para .env)
├── .env                        # Configuração local (não vai para o GitHub)
├── docker-compose.yml          # Para correr com Docker
└── requirements.txt            # Dependências Python
```

---

## Instalação

### 1. Verificar versão de Python
```bash
python --version
# Necessário: Python 3.11 ou superior
```

### 2. Instalar dependências
```bash
cd streamlit
pip install -r requirements.txt
```

### 3. Criar o ficheiro de configuração

O ficheiro `.env` não é incluído no repositório por razões de segurança. Tens de o criar a partir do exemplo:

```bash
cp .env.example .env
```

Abre o `.env` num editor de texto e preenche conforme o backend que queres usar.

---

## Configuração do Backend LLM

O sistema suporta dois backends — escolhe um conforme o teu caso:

### Opção A — Ollama (local, sem internet, recomendado para dados reais)

Ideal para contexto hospitalar porque nenhum dado sai da máquina.

**1. Instalar Ollama**
```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: descarregar em https://ollama.com/download
```

**2. Descarregar o modelo**
```bash
ollama pull llama3.1:8b
```

**3. Configurar o `.env`**
```
LLM_BACKEND=ollama
ACTIVE_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
GROQ_API_KEY=
```

---

### Opção B — Groq (API, ~10x mais rápido, requer internet)

Útil para desenvolvimento e testes rápidos. Os dados são enviados para os servidores da Groq — **não usar com dados reais de doentes**.

**1. Criar conta e obter chave API**
- Aceder a https://console.groq.com
- Criar conta gratuita
- Ir a **API Keys** → **Create API Key**
- Copiar a chave gerada

**2. Configurar o `.env`**
```
LLM_BACKEND=groq
ACTIVE_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=cola_aqui_a_tua_chave
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Correr o Dashboard

O dashboard permite processar qualquer nota clínica de AVC — basta colar o texto ou carregar um ficheiro `.txt`.

```bash
cd streamlit
streamlit run app.py
```

Abre automaticamente em http://localhost:8501

No dashboard podes:
- Carregar uma carta de alta, nota de admissão ou consulta de seguimento (`.txt`)
- Ou colar o texto directamente
- Executar a extracção com um clique
- Ver os resultados por categoria (timestamps, métricas, escalas, categóricas)
- Expandir cada campo para ver o excerto da nota que suportou a extracção

---

## Usar o Pipeline Directamente (sem dashboard)

Para processar uma nota clínica a partir da linha de comandos:

```bash
cd streamlit
python main.py caminho/para/nota.txt
```

O resultado é guardado automaticamente em `streamlit/outputs/` como JSON.

---

## Validação com Ground Truth

A pasta `validate_all.py` permite avaliar o sistema comparando as extracções com valores anotados manualmente (ground truth). Útil para medir precisão, recall e F1 por variável.

### Estrutura esperada dos dados

Cada caso deve estar numa pasta com os seguintes ficheiros:

```
outputs_teste/
├── caso_001/
│   ├── caso_001.txt                        # carta de alta (obrigatório)
│   ├── caso_001_consulta_3meses.txt        # nota de seguimento (opcional)
│   ├── caso_001_mortalidade_30dias.txt     # nota de mortalidade (opcional)
│   └── caso_001_ground_truth.json          # valores correctos anotados
├── caso_002/
│   └── ...
```

### Actualizar o caminho dos dados

No `validate_all.py`, linha `DATA_DIR`, coloca o caminho para a tua pasta de casos:

```python
DATA_DIR = Path("/caminho/para/os/teus/casos")
```

### Comandos

```bash
# Testar com 1 caso
python validate_all.py --backend ollama --cases 1

# Testar um caso específico pelo nome
python validate_all.py --backend ollama --case nome_do_caso

# Correr os primeiros N casos
python validate_all.py --backend ollama --cases 10

# Correr todos os casos
python validate_all.py --backend ollama

# Usar cache (não volta a chamar o LLM, usa resultados já gerados)
python validate_all.py --backend ollama --use-cache
```

### Interpretar o relatório

Para cada variável são calculadas:
- **Precision** — dos valores extraídos, quantos estão correctos
- **Recall** — dos valores que existem no ground truth, quantos foram encontrados
- **F1** — equilíbrio entre precisão e recall (1.0 = perfeito)
- **MAE** — erro absoluto médio em minutos (para timestamps e métricas temporais)

Os relatórios são guardados automaticamente em `validation_reports/` em CSV e Excel.

---

## Adicionar ou Mudar de Modelo

### Via Ollama
```bash
# Ver modelos disponíveis em https://ollama.com/library
ollama pull phi3
ollama pull gemma2:9b
ollama pull mistral
```

Actualizar `ACTIVE_MODEL` no `.env`:
```
ACTIVE_MODEL=phi3
```

### Via Groq
Ver modelos disponíveis em https://console.groq.com/docs/models e actualizar:
```
ACTIVE_MODEL=llama-3.3-70b-versatile
```

### Comparar modelos

Para comparar o desempenho de dois modelos nos mesmos casos:

```bash
# Modelo 1
ACTIVE_MODEL=llama3.1:8b python validate_all.py --backend ollama --cases 20

# Modelo 2
ACTIVE_MODEL=phi3 python validate_all.py --backend ollama --cases 20
```

Os relatórios ficam guardados com timestamp em `validation_reports/` e podem ser comparados directamente.

---

## Tipos de Episódios Suportados

O sistema reconhece e processa correctamente todos os cenários clínicos da Via Verde AVC:

| Tipo | Descrição |
|------|-----------|
| `fibrinolise_pre_hospitalar` | Via Verde pré-hospitalar, tratado com fibrinólise |
| `fibrinolise_pre_hospitalar_ace` | Idem, AVC extenso (TACS) |
| `bridging` | Transferido de outro hospital — fibrinólise na origem + trombectomia em Coimbra |
| `tev_isolada_contraindicacao` | Trombectomia isolada, sem fibrinólise por contraindicação |
| `tev_isolada_fora_janela` | Trombectomia isolada, fora da janela terapêutica |
| `fibrinolise_intra_hospitalar` | AVC durante internamento noutro serviço |
| `conservador_lacunar` | AVC lacunar, tratamento conservador |
| `conservador_wake_up` | Wake-up stroke, tratamento conservador |

---

## Notas

- O ficheiro `.env` **nunca deve ser partilhado** — contém a chave API
- A pasta `streamlit/outputs/` contém os JSONs processados e **não deve ser partilhada** se contiver dados reais
- O `.gitignore` já exclui estes ficheiros
- Para usar com dados reais de doentes, usar sempre Ollama — nunca Groq