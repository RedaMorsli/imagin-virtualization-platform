from fastapi import FastAPI
import uvicorn
from api import auth
from db import init_db


app = FastAPI(title="Auth Server", version="1.0.0")


def start_auth_server(host: str = "0.0.0.0", port: int = 8000):
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    app.include_router(auth.router)
    init_db()
    start_auth_server()