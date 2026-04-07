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

Todo o processamento corre **localmente**, sem enviar dados para fora da máquina — compatível com requisitos RGPD em contexto hospitalar. Os resultados são guardados numa base de dados PostgreSQL e visualizados num dashboard de estatísticas agregadas.

---

## Estrutura do Projecto

```
avc-extraction/
│
├── streamlit/                    # Aplicação principal
│   ├── agents/                   # Agentes de extracção (LLM)
│   │   ├── extractor.py          # Agente 1 — timestamps
│   │   ├── metrics.py            # Agente 2 — métricas temporais (Python puro, sem LLM)
│   │   ├── scales.py             # Agente 3 — escalas NIHSS + mRS
│   │   └── categorical.py        # Agente 4 — variáveis categóricas + mortalidade
│   ├── prompts/                  # Prompts para cada agente
│   │   ├── timestamps_v2.txt     # Prompt de extracção de timestamps
│   │   ├── scales_nihss.txt      # Prompt de extracção NIHSS
│   │   ├── scales_mrs.txt        # Prompt de extracção mRS
│   │   ├── categorical.txt       # Prompt de variáveis categóricas
│   │   └── mortality.txt         # Prompt de mortalidade
│   ├── outputs/                  # JSONs gerados por episódio (criado automaticamente)
│   ├── app.py                    # Página de extracção (Streamlit)
│   ├── dashboard.py              # Página de estatísticas agregadas (Streamlit)
│   ├── database.py               # Ligação e operações PostgreSQL
│   ├── main.py                   # Pipeline principal de extracção
│   ├── Dockerfile                # Container da aplicação Streamlit
│   └── requirements.txt          # Dependências Python
│
├── ollama/                       # Container do servidor LLM local
│   ├── Dockerfile                # Imagem baseada em ollama/ollama
│   └── entrypoint.sh             # Script que faz pull dos modelos no arranque
│
├── validate_all.py               # Validação automática com ground truth
├── fix_ground_truth_bridging.py  # Utilitário de correcção de métricas nos casos bridging
│                                 # (corrige door_to_imaging nos casos bridging se necessário)
│
├── docker-compose.yml            # Orquestração dos 3 containers
├── .env.example                  # Exemplo de configuração (copiar para .env)
├── .env                          # Configuração local (não vai para o GitHub)
└── README.md
```

---

## Pré-requisitos

- Python 3.11 ou superior
- Docker e Docker Compose (para correr com containers)
- Ollama instalado localmente (para desenvolvimento sem Docker)

### Verificar versão de Python
```bash
python --version
```

---

## 1. Configuração inicial — ficheiro `.env`

O ficheiro `.env` não é incluído no repositório por razões de segurança. Cria-o a partir do exemplo:

```bash
cp .env.example .env
```

Abre o `.env` e preenche os valores. O ficheiro tem esta estrutura:

```dotenv
# Backend LLM: "ollama" (local) ou "groq" (API externa)
LLM_BACKEND=ollama

# Modelo activo — mudar para trocar o modelo usado na extracção
ACTIVE_MODEL=llama3.1:8b

# Modelos a descarregar no arranque do Ollama (separados por vírgula)
OLLAMA_MODELS=llama3.1:8b

# URL do Ollama (não alterar se usares docker-compose)
OLLAMA_BASE_URL=http://localhost:11434

# Chave API do Groq (só necessária se LLM_BACKEND=groq)
# Obtém em: https://console.groq.com → API Keys → Create API Key
GROQ_API_KEY=

# Base de dados PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=avc_extraction
POSTGRES_USER=avc_user
POSTGRES_PASSWORD=escolhe_uma_password_segura
```

> ⚠️ O `.env` nunca deve ser partilhado nem ir para o GitHub — contém credenciais.

---

## 2. Instalar dependências Python (desenvolvimento local)

```bash
cd streamlit
pip install -r requirements.txt
```

---

## 3. Configurar o backend LLM

### Opção A — Ollama (local, recomendado para dados reais)

Nenhum dado sai da máquina. Obrigatório para dados reais de doentes.

```bash
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh   # macOS / Linux
# Windows: https://ollama.com/download

# Descarregar o modelo
ollama pull llama3.1:8b

# Verificar que está a correr
ollama list
```

No `.env`, definir:
```
LLM_BACKEND=ollama
ACTIVE_MODEL=llama3.1:8b
```

### Opção B — Groq (API externa, mais rápido, só para testes)

> ⚠️ Os dados são enviados para servidores externos. Nunca usar com dados reais de doentes.

1. Criar conta em https://console.groq.com
2. Ir a **API Keys** → **Create API Key**
3. Copiar a chave para o `.env`:

```
LLM_BACKEND=groq
ACTIVE_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=a_tua_chave_aqui
```

---

## 4. Correr a aplicação

### Opção A — Com Docker (recomendado)

Corre os 3 serviços em simultâneo: PostgreSQL, Ollama e Streamlit.

```bash
# Primeira vez (constrói as imagens e arranca)
docker-compose up --build

# Vezes seguintes
docker-compose up

# Parar
docker-compose down
```

No primeiro arranque, o Ollama faz pull automático dos modelos listados em `OLLAMA_MODELS` — pode demorar alguns minutos dependendo da ligação.

Os modelos ficam guardados em `ollama/models/` (pasta local do projecto) e não se perdem entre reinicios.

> **Se os modelos desaparecerem** (ex: após reinstalar o Docker Desktop), faz pull manualmente:
> ```bash
> docker exec -it avc_ollama ollama pull llama3.1:8b
> ```
> Verifica se ficou instalado:
> ```bash
> docker exec -it avc_ollama ollama list
> # Deve aparecer: llama3.1:8b
> ```

Abre http://localhost:8502 no browser.

### Opção B — Sem Docker (desenvolvimento local)

Precisas de ter o Ollama e o PostgreSQL instalados localmente.

```bash
# Numa janela de terminal — manter o Ollama a correr
ollama serve

# Noutra janela — arrancar o Streamlit
cd streamlit
streamlit run app.py
```

Para o dashboard de estatísticas:
```bash
cd streamlit
streamlit run dashboard.py
```

---

## 5. Usar a aplicação

### Extracção de uma nota clínica

1. Abre http://localhost:8501
2. Na tab **📋 Carta de Alta** — carrega o ficheiro `.txt` ou cola o texto
3. Opcionalmente, adiciona nas outras tabs:
   - **📞 Mortalidade 30 dias** — nota de contacto ou mortalidade
   - **🏥 Consulta 3 meses** — nota de consulta de seguimento
4. Clica **▶️ Executar Extração**
5. Os resultados aparecem organizados por categoria e são guardados automaticamente na base de dados

### Dashboard de estatísticas

Abre http://localhost:8501 e navega para o `dashboard.py`, ou corre:
```bash
streamlit run dashboard.py
```

Mostra estatísticas agregadas de todos os episódios processados: totais, médias de métricas temporais, qualidade ESO, distribuição por tipo e etiologia, mortalidade.

---

## 6. Trocar de modelo

Para testar um modelo diferente:

1. Editar o `.env`:
```dotenv
ACTIVE_MODEL=phi3
OLLAMA_MODELS=llama3.1:8b,phi3
```

2. Se estiver a usar Docker, reiniciar o Ollama:
```bash
docker-compose restart ollama
```

3. Se estiver a usar Ollama local:
```bash
ollama pull phi3
```

Modelos disponíveis via Ollama: https://ollama.com/library  
Modelos disponíveis via Groq: https://console.groq.com/docs/models

---

## 7. Validação automática com ground truth

Permite avaliar a precisão do sistema comparando as extracções com valores anotados manualmente.

### Estrutura esperada dos dados

```
casos/
├── caso_001/
│   ├── caso_001.txt                         # carta de alta (obrigatório)
│   ├── caso_001_consulta_3meses.txt         # nota de seguimento (opcional)
│   ├── caso_001_mortalidade_30dias.txt      # nota de mortalidade (opcional)
│   └── caso_001_ground_truth.json           # valores correctos anotados
├── caso_002/
│   └── ...
```

### Configurar o caminho dos dados

No `validate_all.py`, linha `DATA_DIR`, definir o caminho para a pasta de casos:

```python
DATA_DIR = Path("/caminho/para/os/casos")
```

### Comandos

```bash
# Testar com 1 caso
python validate_all.py --backend ollama --cases 1

# Testar um caso específico
python validate_all.py --backend ollama --case nome_do_caso

# Correr os primeiros N casos
python validate_all.py --backend ollama --cases 30

# Correr todos os casos
python validate_all.py --backend ollama

# Usar cache (reutiliza JSONs já gerados, não chama o LLM)
python validate_all.py --backend ollama --use-cache
```

> ⚠️ Garantir que o Ollama está a correr antes de executar o validate.

### Interpretar o relatório

| Métrica | Significado |
|---|---|
| **Precision** | Dos valores extraídos, quantos estão correctos |
| **Recall** | Dos valores que existem no ground truth, quantos foram encontrados |
| **F1** | Equilíbrio entre precisão e recall (1.0 = perfeito) |
| **MAE** | Erro absoluto médio em minutos (timestamps e métricas) |

Os relatórios são guardados em `validation_reports/` em CSV e Excel.

### Correr em blocos (para não aquecer o PC)

```bash
python validate_all.py --backend ollama --cases 30
# pausa 10-15 min
python validate_all.py --backend ollama --cases 60 --use-cache
# pausa 10-15 min
python validate_all.py --backend ollama --cases 90 --use-cache
# pausa 10-15 min
python validate_all.py --backend ollama --cases 120 --use-cache
# pausa 10-15 min
python validate_all.py --backend ollama --use-cache
```

---

## 8. Comparação de modelos

Para comparar o desempenho de diferentes modelos:

```bash
# Modelo 1
ACTIVE_MODEL=llama3.1:8b python validate_all.py --backend ollama --cases 30

# Modelo 2
ACTIVE_MODEL=phi3 python validate_all.py --backend ollama --cases 30
```

Os relatórios ficam guardados com timestamp em `validation_reports/` para comparação directa.

---

## 9. Tipos de episódios suportados

| Tipo | Descrição |
|------|-----------|
| `fibrinolise_pre_hospitalar` | Via Verde pré-hospitalar, fibrinólise |
| `fibrinolise_pre_hospitalar_ace` | Idem, AVC extenso (TACS) |
| `bridging` | Transferido de outro hospital — fibrinólise na origem + trombectomia em Coimbra |
| `tev_isolada_contraindicacao` | Trombectomia isolada, sem fibrinólise por contraindicação |
| `tev_isolada_fora_janela` | Trombectomia isolada, fora da janela terapêutica |
| `fibrinolise_intra_hospitalar` | AVC durante internamento noutro serviço |
| `conservador_lacunar` | AVC lacunar, tratamento conservador |
| `conservador_wake_up` | Wake-up stroke, tratamento conservador |

---

## Notas importantes

- O `.env` **nunca deve ir para o GitHub** — está no `.gitignore`
- A pasta `streamlit/outputs/` contém JSONs processados — não partilhar se contiver dados reais
- Para dados reais de doentes, usar sempre **Ollama** — nunca Groq
- O Ollama deve estar a correr antes de executar o `validate_all.py` ou o Streamlit

---

## Modelos no Docker — nota importante

Os modelos do Ollama são guardados na pasta **`ollama/models/`** do projecto. Esta pasta é montada como volume no container e persiste entre reinicios normais do Docker.

Se a pasta estiver vazia (primeira vez, ou após reset do Docker Desktop), fazer pull manualmente:

```bash
docker exec -it avc_ollama ollama pull llama3.1:8b
```

Verificar se o modelo está disponível:
```bash
docker exec -it avc_ollama ollama list
```

Para adicionar um novo modelo ao Docker:
```bash
# 1. Adicionar ao .env
OLLAMA_MODELS=llama3.1:8b,phi3

# 2. Fazer pull dentro do container
docker exec -it avc_ollama ollama pull phi3

# 3. Mudar o modelo activo no .env e rebuildar o streamlit
ACTIVE_MODEL=phi3
docker-compose up --build streamlit
```