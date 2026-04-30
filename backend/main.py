from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from api import auth, project, infra, registry, storage, experiment
from db import init_db
import infra.fl_docker as fl_docker


app = FastAPI(title="Auth Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers immediately so uvicorn main:app has all endpoints.
app.include_router(auth.router)
app.include_router(project.router)
app.include_router(infra.router)
app.include_router(registry.router)
app.include_router(storage.router)
app.include_router(experiment.router)


@app.on_event("startup")
def startup_tasks():
    init_db()
    try:
        fl_docker.ensure_worker_image()
    except Exception as exc:
        print(f"warning: FL worker image build failed at startup: {exc}")
    try:
        reconciliation = infra.reconcile_provisions()
        print(
            "Provision reconciliation complete: "
            f"reconciled={reconciliation['reconciled']}, "
            f"updated={reconciliation['updated']}, "
            f"errors={reconciliation['errors']}"
        )
    except Exception as exc:
        print(f"warning: provision reconciliation failed at startup: {exc}")


def start_auth_server(host: str = "0.0.0.0", port: int = 8000):
    print("Starting server...")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    start_auth_server()
