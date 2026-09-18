from fastapi import FastAPI

app = FastAPI(title="DRL2 API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "drl2-api"}
