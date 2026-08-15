# beyond_crud
FastAPI Production Journey

Phase-by-phase build documented in [`.claude/Master_FastAPI_BookMarkAPI.md`](.claude/Master_FastAPI_BookMarkAPI.md).

## Setup

```bash
conda activate beyondcrud
pip install -r requirements.txt
```

## Run (Phase 0)

```bash
uvicorn app.main:app --reload
```

Then explore:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/health
