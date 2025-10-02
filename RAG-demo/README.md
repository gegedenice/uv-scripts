# RAG-Notify Demo

**RAG over LDN** : distributed-RAG with Json-LD normalized-notifications Hub

- Distributed and deported : plus besoin d’un “RAG monolithique”, mais une constellation de micro-services qui communiquent via notifications standardisées.

- Event-driven federated Index: les index sont toujours à jour, réactifs.
  - Chaque ressource/document expose un inbox.
  - Quand une nouvelle version est créée ou modifiée, elle envoie une Create ou Update notification.
  - Le consumer (ex. un micro-service embedder.py) reçoit la notif → re-vectorise uniquement ce qui a changé.

- De boîte noire → traçabilité native : chaque opération est notifiée et archivée.

- De format fermé → web sémantique : les notifs sont du JSON-LD, donc interopérables avec les graphes existants.

## Project structure

```
RAG-notify-demo/
 ├─ README.md
 ├─ inbox_server.py         # petite Inbox LDN (HTTP) pour le POC
 ├─ send_ldn.py             # envoi d'une notif vers l'inbox
 ├─ poll_and_run.py         # runner: lit notifs → orchestre scripts
 ├─ splitter.py             # découpe document → chunks.jsonl
 ├─ embedder.py             # chunks → embeddings.jsonl
 ├─ indexer.py              # embeddings → index.jsonl
 ├─ query.py                # question → résultats depuis index.jsonl
 ├─ examples/
 │   ├─ sample.txt
 │   └─ job.create.json     # payload LDN de départ
 └─ state/                  # sortie du POC (chunks, embeddings, index)
```

## Run

1. Launch Inbox (terminal A)
```
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/refs/heads/ba571958a173624d977c949601bab53800cf695a/RAG-demo/inbox_server.py
```

2. Send the Create notif

```
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/refs/heads/ba571958a173624d977c949601bab53800cf695a/RAG-demo/send_ldn.py \
  --inbox http://localhost:8080/inbox \
  --payload https://raw.githubusercontent.com/gegedenice/uv-scripts/refs/heads/ba571958a173624d977c949601bab53800cf695a/RAG-demo/examples/job.create.json
```

3. Launch the runner (orchestrator) (terminal B)

```
INBOX_URL=http://localhost:8080/inbox \
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/refs/heads/ba571958a173624d977c949601bab53800cf695a/RAG-demo/poll_and_run.py
```

4. Query the Index

```
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/refs/heads/ba571958a173624d977c949601bab53800cf695a/RAG-demo/query.py --index state/index.jsonl \
  --q "De quoi parle le document ?" --k 5
```