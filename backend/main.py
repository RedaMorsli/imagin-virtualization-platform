from fastapi import FastAPI
import uvicorn
from api import auth, project, infra, registry
from db import init_db


app = FastAPI(title="Auth Server", version="1.0.0")

# Register routers immediately so uvicorn main:app has all endpoints.
app.include_router(auth.router)
app.include_router(project.router)
app.include_router(infra.router)
app.include_router(registry.router)


def start_auth_server(host: str = "0.0.0.0", port: int = 8000):
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    init_db()
    start_auth_server()
