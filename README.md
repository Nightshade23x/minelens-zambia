# MineLens Zambia

MineLens Zambia is a Python-based mining information retrieval and question-answering project focused on public information about Zambia's mining sector. It combines searchable documents with structured mining data and uses a locally hosted language model for evidence-grounded answers.

## What it does

- Routes questions to document search, mining licensing information, structured facility records or mining statistics.
- Combines keyword and semantic retrieval for relevant source passages.
- Generates source-aware answers using retrieved evidence and a local Ollama model.
- Supports raw retrieval output for inspecting results and evidence selection.
- Includes ingestion, evaluation and test code.

## Tech stack

Python; BM25 and sentence embeddings for retrieval; local Ollama inference; structured mining data and document-processing pipelines.

## Setup

Requires Python, the project's data/index files, and an available Ollama installation for generated answers.

```powershell
git clone https://github.com/Nightshade23x/minelens-zambia.git
cd minelens-zambia
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start Ollama separately and ensure an appropriate instruction-tuned model is installed. Then ask a question:

```powershell
python -m app.main "Who operates Kansanshi mine?"
```

Inspect retrieval without generating an answer:

```powershell
python -m app.main "Copper processing facilities in the Copperbelt" --raw
```

You can set a model explicitly with `--model MODEL_NAME` or control retrieval with `--top-k` and `--evidence-k`.

## Repository structure

- `app/` — query routing, retrieval and grounded answering.
- `ingestion/` — document acquisition and processing.
- `database/`, `data/` — structured sources and local data assets.
- `evaluation/`, `tests/` — quality checks and regression tests.
- `frontend/` — user interface code.
- `config/`, `scripts/` — configurations and utilities.

## Limitations

Results depend on available source coverage and document freshness; generated text should be checked against its cited evidence. The project is a research/prototype tool and should not be used as the sole basis for legal, licensing or investment decisions.
