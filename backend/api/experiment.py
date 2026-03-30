import json
import os
import threading

from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth
from api.project import user_has_project_access
import infra.fl_docker as fl_docker

router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
)

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://backend:8000")


# ============ SCHEMAS ============

class CreateExperimentRequest(BaseModel):
    project_id: int
    experiment_type: str
    experiment_config: dict


class DeleteExperimentRequest(BaseModel):
    project_id: int
    experiment_id: int


class LaunchRunRequest(BaseModel):
    experiment_id: int


class RunMetricsRequest(BaseModel):
    run_id: int
    round: int
    metrics: dict


class RunCompleteRequest(BaseModel):
    run_id: int
    status: str


# ============ ENDPOINTS ============

@router.post("/create")
async def create_experiment_endpoint(request: CreateExperimentRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        _create_experiment(user["user_id"], request.project_id, request.experiment_type, request.experiment_config)
        return Response(status_code=status.HTTP_200_OK)
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/fetch")
async def fetch_experiments_endpoint(project_id: int, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        return _fetch_experiments(user["user_id"], project_id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/delete")
async def delete_experiment_endpoint(request: DeleteExperimentRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        _delete_experiment(user["user_id"], request.project_id, request.experiment_id)
        return Response(status_code=status.HTTP_200_OK)
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/runs/launch")
async def launch_run_endpoint(request: LaunchRunRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        run_id       = _create_run(user["user_id"], request.experiment_id)
        config       = _get_experiment_config(request.experiment_id)
        project_name = _get_project_name_for_experiment(request.experiment_id)
        threading.Thread(
            target=_background_launch,
            args=(run_id, config, project_name),
            daemon=True,
        ).start()
        return {"run_id": run_id}
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/runs/fetch")
async def fetch_runs_endpoint(experiment_id: int, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        return _fetch_runs(user["user_id"], experiment_id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# Called by the FL server container — no user auth, identified by run_id.
@router.post("/runs/metrics")
async def run_metrics_endpoint(request: RunMetricsRequest):
    for name, value in request.metrics.items():
        db.execute(
            "INSERT INTO RunMetrics (run_id, round, metric_name, metric_value) VALUES (?, ?, ?, ?)",
            [request.run_id, request.round, name, float(value)],
        )
    return Response(status_code=status.HTTP_200_OK)


# Called by the FL server container when all rounds are done.
@router.post("/runs/complete")
async def run_complete_endpoint(request: RunCompleteRequest):
    db.execute(
        "UPDATE ExperimentRuns SET status = ?, finished_at = now() WHERE run_id = ?",
        [request.status, request.run_id],
    )
    threading.Thread(
        target=fl_docker.teardown_run,
        args=(request.run_id,),
        daemon=True,
    ).start()
    return Response(status_code=status.HTTP_200_OK)


# ============ LOGIC ============

def _create_experiment(user_id: int, project_id: int, experiment_type: str, experiment_config: dict):
    if not user_has_project_access(user_id, project_id):
        raise PermissionError("User does not have access to this project")
    name = experiment_config.get("name", "").strip()
    if not name:
        raise ValueError("Experiment name is required")
    existing = db.fetch_all(
        "SELECT 1 FROM Experiments WHERE experiment_name = ? AND project_id = ?",
        [name, project_id],
    )
    if existing:
        raise ValueError("An experiment with this name already exists in the project")
    db.execute(
        "INSERT INTO Experiments (project_id, experiment_name, experiment_type, experiment_config) VALUES (?, ?, ?, ?)",
        [project_id, name, experiment_type, json.dumps(experiment_config)],
    )


def _delete_experiment(user_id: int, project_id: int, experiment_id: int):
    if not user_has_project_access(user_id, project_id):
        raise PermissionError("User does not have access to this project")
    # Teardown any active runs before deleting
    active_runs = db.fetch_all(
        "SELECT run_id FROM ExperimentRuns WHERE experiment_id = ? AND status IN ('provisioning', 'running')",
        [experiment_id],
    )
    for (run_id,) in active_runs:
        threading.Thread(target=fl_docker.teardown_run, args=(run_id,), daemon=True).start()
        db.execute(
            "UPDATE ExperimentRuns SET status = 'failed', finished_at = now() WHERE run_id = ?",
            [run_id],
        )
    db.execute("DELETE FROM RunMetrics WHERE run_id IN (SELECT run_id FROM ExperimentRuns WHERE experiment_id = ?)", [experiment_id])
    db.execute("DELETE FROM ExperimentRuns WHERE experiment_id = ?", [experiment_id])
    db.execute("DELETE FROM Experiments WHERE experiment_id = ? AND project_id = ?", [experiment_id, project_id])


def _fetch_experiments(user_id: int, project_id: int) -> dict:
    if not user_has_project_access(user_id, project_id):
        raise PermissionError("User does not have access to this project")
    rows = db.fetch_all(
        "SELECT experiment_id, experiment_name, experiment_type, experiment_config FROM Experiments WHERE project_id = ?",
        [project_id],
    )
    experiments = []
    for exp_id, exp_name, exp_type, exp_config_raw in rows:
        runs = _fetch_runs_for_experiment(exp_id)
        experiments.append({
            "experiment_id":     exp_id,
            "experiment_name":   exp_name,
            "experiment_type":   exp_type,
            "experiment_config": json.loads(exp_config_raw),
            "runs":              runs,
        })
    return {"experiments": experiments}


def _fetch_runs(user_id: int, experiment_id: int) -> dict:
    rows = db.fetch_all(
        "SELECT project_id FROM Experiments WHERE experiment_id = ?",
        [experiment_id],
    )
    if not rows:
        raise ValueError("Experiment not found")
    project_id = rows[0][0]
    if not user_has_project_access(user_id, project_id):
        raise PermissionError("User does not have access to this project")
    return {"runs": _fetch_runs_for_experiment(experiment_id)}


def _fetch_runs_for_experiment(experiment_id: int) -> list:
    rows = db.fetch_all(
        """
        SELECT run_id, status, run_config, started_at, finished_at
        FROM ExperimentRuns
        WHERE experiment_id = ?
        ORDER BY started_at DESC
        """,
        [experiment_id],
    )
    result = []
    for run_id, run_status, run_config_raw, started_at, finished_at in rows:
        metrics_rows = db.fetch_all(
            """
            SELECT round, metric_name, metric_value
            FROM RunMetrics
            WHERE run_id = ?
            ORDER BY round, metric_name
            """,
            [run_id],
        )
        # Build per-round metric dict and also extract final values
        rounds: dict = {}
        for r, name, val in metrics_rows:
            rounds.setdefault(r, {})[name] = val
        final_metrics = rounds[max(rounds)] if rounds else {}

        result.append({
            "run_id":        run_id,
            "status":        run_status,
            "run_config":    json.loads(run_config_raw),
            "started_at":    str(started_at) if started_at else None,
            "finished_at":   str(finished_at) if finished_at else None,
            "rounds_data":   rounds,
            "final_metrics": final_metrics,
        })
    return result


def _create_run(user_id: int, experiment_id: int) -> int:
    rows = db.fetch_all(
        "SELECT project_id FROM Experiments WHERE experiment_id = ?",
        [experiment_id],
    )
    if not rows:
        raise ValueError("Experiment not found")
    project_id = rows[0][0]
    if not user_has_project_access(user_id, project_id):
        raise PermissionError("User does not have access to this project")
    db.execute(
        "INSERT INTO ExperimentRuns (experiment_id, run_config, status) VALUES (?, ?, 'provisioning')",
        [experiment_id, json.dumps({})],
    )
    # Retrieve the just-inserted run_id by selecting the latest for this experiment
    id_rows = db.fetch_all(
        "SELECT run_id FROM ExperimentRuns WHERE experiment_id = ? ORDER BY started_at DESC LIMIT 1",
        [experiment_id],
    )
    return id_rows[0][0]


def _get_experiment_config(experiment_id: int) -> dict:
    rows = db.fetch_all(
        "SELECT experiment_config FROM Experiments WHERE experiment_id = ?",
        [experiment_id],
    )
    if not rows:
        return {}
    return json.loads(rows[0][0])


def _get_project_name_for_experiment(experiment_id: int) -> str:
    rows = db.fetch_all(
        """
        SELECT p.project_name
        FROM Projects p
        JOIN Experiments e ON e.project_id = p.project_id
        WHERE e.experiment_id = ?
        """,
        [experiment_id],
    )
    return rows[0][0] if rows else ""


def _background_launch(run_id: int, config: dict, project_name: str = "") -> None:
    try:
        fl_docker.ensure_worker_image()
        fl_docker.launch_run(run_id, config, PLATFORM_URL, project_name)
        db.execute(
            "UPDATE ExperimentRuns SET status = 'running' WHERE run_id = ?",
            [run_id],
        )
    except Exception as exc:
        print(f"[experiment] FL run {run_id} failed to launch: {exc}")
        db.execute(
            "UPDATE ExperimentRuns SET status = 'failed', finished_at = now() WHERE run_id = ?",
            [run_id],
        )
