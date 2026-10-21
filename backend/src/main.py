"""FastAPI Application factory and server entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router
import src.transforms.builtin  # Registers standard DNS & network transforms

app = FastAPI(
    title="Sherlock AI API",
    description="Clean-room graph-first link analysis and OSINT investigation engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="127.0.0.1", port=8080, reload=True)
