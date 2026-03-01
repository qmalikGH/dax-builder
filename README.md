# DAX Builder

AI-gestützter DAX Measure Generator für Power BI. Beschreibe ein Measure in natürlicher Sprache – der AI schreibt den DAX-Code.

<!-- Screenshot Platzhalter – ersetze mit echtem Screenshot nach erstem Deployment -->
<!-- ![DAX Builder Screenshot](docs/screenshot.png) -->

## Features

- **Demo-Modus** – sofort nutzbar ohne eigenes Modell (Dummy-Finanzdaten)
- **ZIP-Upload** – eigene Power BI TMDL Definition hochladen
- **Anonymisierung** – echte Tabellen-/Spaltennamen werden vor dem AI-Aufruf ersetzt
- **Multi-Turn** – Kontext über mehrere Anfragen hinweg erhalten
- **Multi-Provider** – Anthropic Claude, Azure OpenAI oder lokales Ollama

---

## Lokale Installation

### Voraussetzungen

- Python 3.11 oder neuer ([python.org](https://www.python.org/downloads/))
- Ein Anthropic API Key ([console.anthropic.com](https://console.anthropic.com))

### Schritte

```bash
# 1. Repository klonen
git clone https://github.com/DEIN-BENUTZERNAME/dax-builder.git
cd dax-builder

# 2. Virtuelle Umgebung erstellen
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. API Key setzen (.env Datei erstellen)
# Windows
echo ANTHROPIC_API_KEY=sk-ant-... > .env
# macOS / Linux
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 5. App starten
streamlit run dax_builder.py
```

Die App öffnet sich automatisch unter `http://localhost:8501`.

### Optionale .env Einstellungen

```env
# AI Provider (anthropic | azure | ollama)
AI_PROVIDER=anthropic

# Modell
AI_MODEL=claude-sonnet-4-5

# Nur für Azure OpenAI:
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-02-01

# Nur für Ollama:
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Power BI Modell hochladen

1. In Power BI Desktop: **File → Save As → Power BI Project (.pbip)**
2. Im Projektordner befindet sich ein `definition/` Ordner
3. Diesen Ordner als ZIP packen (z.B. `definition.zip`)
4. In der App unter **Setup** hochladen

Erwartete ZIP-Struktur:
```
definition.zip
└── definition/
    ├── model.tmdl
    ├── relationships.tmdl
    └── tables/
        ├── Umsatz.tmdl
        ├── Kalender.tmdl
        └── ...
```

---

## Deployment auf Streamlit Cloud

### Schritte

1. **Repository auf GitHub pushen**
   ```bash
   git add .
   git commit -m "Initial DAX Builder"
   git push origin main
   ```

2. **App anlegen auf [share.streamlit.io](https://share.streamlit.io)**
   - *New app* → GitHub Repository auswählen
   - Main file: `dax_builder.py`
   - *Deploy*

3. **API Key als Secret hinterlegen**
   - In der App-Übersicht: **Settings → Secrets**
   - Einfügen:
     ```toml
     ANTHROPIC_API_KEY = "sk-ant-..."
     ```
   - *Save* → App startet neu

Die App ist dann erreichbar unter `https://DEIN-NAME-dax-builder.streamlit.app`.

> Kein `.env` File nötig – Streamlit Cloud injiziert die Secrets automatisch als Umgebungsvariablen.

---

## Projektstruktur

```
dax_builder.py        # Streamlit App (Haupteinstiegspunkt)
mapping_generator.py  # Liest PBIP/TMDL Modell, erzeugt Mapping
anonymizer.py         # Anonymisiert Prompts, de-anonymisiert Antworten
ai_client.py          # AI-Provider Abstraktion (Anthropic / Azure / Ollama)
requirements.txt      # Python-Abhängigkeiten
.gitignore            # Schließt .env, mapping.json und temp-Ordner aus
```

---

## Wie Anonymisierung funktioniert

Vor dem AI-Aufruf:
1. `anonymizer.py` ersetzt echte Namen (`Finanzdaten` → `Table_A`, `Betrag_netto` → `Col_A2` …)
2. Der anonymisierte Prompt geht an die AI
3. Die Antwort (mit Aliasen) kommt zurück
4. Aliase werden vor der Anzeige wieder ersetzt

Dein echtes Datenschema verlässt die Umgebung nie im Klartext.

---

## AI Provider wechseln

Einstellung in `.env` (lokal) oder Streamlit Secrets (Cloud):

| Provider | Einstellung |
|----------|-------------|
| Anthropic Claude | `AI_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...` |
| Azure OpenAI | `AI_PROVIDER=azure`, `AZURE_OPENAI_ENDPOINT=...`, `AZURE_OPENAI_API_KEY=...` |
| Ollama (lokal) | `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434`, `AI_MODEL=llama3` |

---

## Lizenz

MIT
