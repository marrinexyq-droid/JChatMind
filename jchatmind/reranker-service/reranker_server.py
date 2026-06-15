"""
Local Cross-Encoder Reranker Service
Uses sentence-transformers to load BAAI/bge-reranker-v2-m3 (or any HF reranker).
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import CrossEncoder

MODEL_ID = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
DEVICE = os.getenv("RERANK_DEVICE", "auto")  # "cpu", "cuda", or "auto"

model: CrossEncoder | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print(f"Loading reranker model: {MODEL_ID} (device={DEVICE}) ...")
    model = CrossEncoder(MODEL_ID, device=DEVICE if DEVICE != "auto" else None)
    print("Reranker model loaded.")
    yield
    print("Shutting down reranker service.")


app = FastAPI(title="Local Reranker", lifespan=lifespan)


class RerankRequest(BaseModel):
    query: str
    documents: list[str]


class RerankResult(BaseModel):
    index: int
    score: float


@app.post("/rerank", response_model=list[RerankResult])
def rerank(req: RerankRequest):
    if model is None:
        raise HTTPException(503, "Model not loaded yet")

    if not req.documents:
        return []

    if not req.query:
        raise HTTPException(400, "query cannot be empty")

    MAX_LEN = 500
    safe_docs = [d[:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  ] for d in req.documents]
    pairs = [(req.query, doc) for doc in safe_docs]
    scores = model.predict(pairs, convert_to_tensor=True)

    results = []
    for i, score in enumerate(scores):
        results.append(RerankResult(index=i, score=round(float(score), 6)))

    results.sort(key=lambda r: r.score, reverse=True)
    return results


@app.get("/health")
def health():
    return {"status": "ok" if model else "loading"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("RERANK_PORT", "8001"))
    uvicorn.run(app, host="127.0.0.1", port=port)
