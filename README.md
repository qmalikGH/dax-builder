# DAX Builder

AI-powered DAX measure generator for Power BI.
Describe what you need in plain German or English – the app generates the DAX code and explains it.

---

## Features

- Natural-language → DAX measure generation
- Privacy-first: real table/column names are **anonymized** before sending to the AI
- Multi-provider: switch between **Anthropic Claude**, **Azure OpenAI**, and local **Ollama** with a single `.env` change
- Conversation history: previous measures stay in context so the AI can build on them
- One-click clipboard copy for every generated measure
- Sidebar model overview: tables, columns, measures, relationships

---

## Installation

### 1. Prerequisites

- Python 3.11 or newer
- pip

### 2. Clone / download

```bash
git clone <your-repo-url>
cd dax-builder
```

### 3. Create a virtual environment (recommended)

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure the AI provider

Copy (or edit) `.env` and fill in your credentials:

```bash
# For Anthropic Claude (default)
ANTHROPIC_API_KEY=sk-ant-...
AI_PROVIDER=anthropic
AI_MODEL=claude-sonnet-4-5
```

Get an Anthropic API key at: <https://console.anthropic.com/>

### 6. Generate the mapping file

```bash
# Generates a dummy mapping.json for the sample financial model
python mapping_generator.py

# Or from a real Power BI model.bim file
python mapping_generator.py --source path/to/model.bim
```

> **Note:** `mapping.json` is excluded from git (`.gitignore`) because it may contain business-sensitive schema information.

### 7. Start the app

```bash
streamlit run dax_builder.py
```

The browser opens automatically at `http://localhost:8501`.

---

## Switching AI Providers

Edit `.env` – no code changes required:

| Provider | Settings |
|----------|----------|
| Anthropic Claude | `AI_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...` |
| Azure OpenAI | `AI_PROVIDER=azure`, `AZURE_OPENAI_ENDPOINT=...`, `AZURE_OPENAI_API_KEY=...` |
| Ollama (local) | `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434`, `AI_MODEL=llama3` |

---

## Project Structure

```
dax-builder/
├── dax_builder.py          # Streamlit web app (main entry point)
├── mapping_generator.py    # Generates mapping.json from model.bim or dummy data
├── anonymizer.py           # Anonymizes prompts, deanonymizes responses
├── ai_client.py            # Multi-provider AI abstraction layer
├── requirements.txt
├── .env                    # API keys & provider config (not in git)
├── mapping.json            # Generated schema mapping (not in git)
├── .gitignore
└── README.md
```

---

## Usage Example

1. Open the app in your browser
2. Enter a description like:
   *"Berechne den Nettoumsatz für das aktuelle Geschäftsjahr, aufgeteilt nach Kostenstellen, nur für aktive Kostenstellen."*
3. Click **DAX generieren**
4. Copy the generated measure with **In Clipboard kopieren**
5. Paste it directly into Power BI Desktop

---

## How Anonymization Works

Before sending your request to the AI:

1. `anonymizer.py` replaces real names (`Finanzdaten` → `Table_A`, `Betrag_netto` → `Col_A2`, …)
2. The anonymized prompt is sent to the AI
3. The response (with aliases) is received back
4. Aliases are replaced with real names before display

This means your real business schema never leaves your network (beyond the AI API call),
and even the AI sees only generic placeholder names.

---

## Smoke Tests

```bash
# Test mapping generation
python mapping_generator.py

# Test anonymizer
python anonymizer.py

# Test AI client
python ai_client.py
```

---

## License

MIT
