from fastapi import FastAPI

app = FastAPI(title="Edlo API")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status" : "Ok"}