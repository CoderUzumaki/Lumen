# Backend scripts

One-off maintenance, migration, and seed scripts. None of these are imported by the running application. Run them from the `backend/` directory:

```bash
python -m scripts.<name>
```

| Script | Purpose | Idempotent? | Destructive? |
|---|---|---|---|
| `populate_db.py` | Seed the DB with English-vendor sample transactions for `user_id='123'`. | No — appends duplicates each run. | No |
| `reset_and_populate_inr.py` | Wipe `transactions` / `transaction_items` and reseed with Indian-vendor data for `user_id='123'`. | No | **Yes — deletes existing transactions for user 123.** |
| `backfill_chromadb.py` | Re-embed every existing transaction into ChromaDB for RAG. Run after schema changes that affect embedded text. | Safe to re-run; produces duplicates today (see TODO `AI-05`). | No |
| `create_email_tables.py` | Calls `db.create_all()` — useful when adding the `EmailConfig` table to an older DB. | Yes | No |
| `fix_anomalies_table.py` | Drop and recreate `anomalies` table with the current schema. | Yes | **Yes — drops `anomalies` table.** |
| `fix_insights_table.py` | Drop and recreate `insights` table with the current schema. | Yes | **Yes — drops `insights` table.** |
| `check_transactions.py` | Print a per-month summary of transactions for `user_id='123'`. Read-only. | Yes | No |
| `check_reminders.py` | Print detected spending patterns and reminder candidates for today. Read-only. | Yes | No |

## When to use which

- **Fresh dev environment**: start `app.py` once (creates the schema), then `python -m scripts.reset_and_populate_inr` for INR demo data, or `python -m scripts.populate_db` for the English dataset.
- **After changing transaction model fields**: run `python -m scripts.backfill_chromadb` to refresh vector embeddings.
- **After changing `Anomaly` or `Insight` model fields**: run the corresponding `fix_*_table.py` (these drop and recreate, so data is lost).

## Caveats

- All seed scripts hardcode `user_id='123'`. Replace with a real user id once authentication lands (TODO `AUTH-03`/`AUTH-05`).
- These scripts are **not** part of the production startup path. Do not run any of them from a production shell unless you understand the destructive ones.
- `fix_*` scripts use raw SQL with a hardcoded schema definition. If the SQLAlchemy model in `models/__init__.py` drifts from that SQL, fix both in lockstep — better still, replace them with proper Alembic migrations (TODO `DB-03` follow-up).
