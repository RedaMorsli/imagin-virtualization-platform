
from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth
import json
import infra.k8s as k8s
import infra.provisions as provisions_registry
from api.project import user_has_project_access

router = APIRouter(
    prefix="/infra",
    tags=["infra"],
)


# ============ SCHEMAS ============

class CreateInfraRequest(BaseModel):
    project_id: int
    infra_type: str
    infra_config: dict
    provisions: list[dict] = []


class DeleteInfraRequest(BaseModel):
    project_id: int
    infra_id: int


class FetchInfraRequest(BaseModel):
    project_id: int


class FetchInfraResponse(BaseModel):
    infras: list[dict]


class KubeconfigRequest(BaseModel):
    project_id: int
    infra_id: int


class KubeconfigResponse(BaseModel):
    kubeconfig: str


# ============ ENDPOINTS ============


@router.post("/create")
async def create_infra_endpoint(request: CreateInfraRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        _create_infra(
            user['user_id'],
            request.project_id,
            request.infra_type,
            request.infra_config,
            request.provisions,
        )
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/delete")
async def delete_infra_endpoint(request: DeleteInfraRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        _delete_infra(user['user_id'], request.project_id, request.infra_id)
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/fetch", response_model=FetchInfraResponse)
async def fetch_infras_endpoint(project_id: int, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _fetch_infras(user['user_id'], project_id)
        return FetchInfraResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/kubeconfig", response_model=KubeconfigResponse)
async def fetch_kubeconfig_endpoint(request: KubeconfigRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _get_kubeconfig(user['user_id'], request.project_id, request.infra_id)
        return KubeconfigResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


# ============ LOGIC ============


def _resolve_cluster_name(infra_name: str | None, infra_config: dict) -> str:
    by_config = str(infra_config.get("name", "")).strip()
    if by_config:
        return by_config

    by_row_name = str(infra_name or "").strip()
    if by_row_name:
        return by_row_name

    context = str(infra_config.get("context", "")).strip()
    if context.startswith("k3d-") and len(context) > 4:
        return context[4:]
    if context:
        return context

    raise ValueError("Cluster name not found for infra")


def _normalize_provisions(
    project_id: int,
    infra_name: str | None,
    infra_config: dict,
    raw_provisions: list[dict] | None,
) -> list[dict]:
    """Validate provision entries, attach the per-provision _seed, and inject a
    legacy-compat headlamp entry when only the old `web_ui` flag is set."""
    resolved: list[dict] = []
    seen_types: set[str] = set()
    for entry in raw_provisions or []:
        if not isinstance(entry, dict):
            raise ValueError("each provision must be an object")
        p_type = entry.get("type")
        if not p_type:
            raise ValueError("provision is missing 'type'")
        if not provisions_registry.has(p_type):
            raise ValueError(f"unknown provision type '{p_type}'")
        cfg = dict(entry.get("config") or {})
        cfg["_seed"] = {"project_id": project_id, "infra_name": infra_name}
        resolved.append({"type": p_type, "config": cfg})
        seen_types.add(p_type)

    if "headlamp" not in seen_types and infra_config.get("web_ui") is True:
        cfg = {
            "port": infra_config.get("web_ui_port", k8s.HEADLAMP_NODE_PORT),
            "_seed": {"project_id": project_id, "infra_name": infra_name},
        }
        resolved.append({"type": "headlamp", "config": cfg})

    return resolved


def _strip_seed(config: dict) -> dict:
    return {k: v for k, v in config.items() if k != "_seed"}


def _resolve_registry_for_cluster(project_id: int, infra_config: dict) -> str | None:
    raw = infra_config.get("registry_infra_id")
    if raw is None:
        return None
    try:
        registry_infra_id = int(raw)
    except (TypeError, ValueError):
        raise ValueError("'registry_infra_id' must be an integer") from None

    rows = db.fetch_all(
        """
        SELECT infra_config
        FROM Infra
        WHERE infra_id = ? AND infra_type = ? AND project_id = ?
        """,
        params=[registry_infra_id, "registry", project_id],
    )
    if not rows:
        raise ValueError("Registry infra not found for provided id")

    try:
        registry_config = json.loads(rows[0][0])
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Stored registry config is invalid") from exc

    registry_name = registry_config.get("name")
    if not registry_name:
        raise ValueError("Registry infra config missing 'name'")
    registry_port = registry_config.get("port", 5000)
    return f"k3d-{registry_name}:{registry_port}"


def _create_infra(
    user_id: int,
    project_id: int,
    infra_type: str,
    infra_config: dict,
    provisions: list[dict] | None,
):
    if not user_has_project_access(user_id, project_id):
        raise ValueError("User does not have access to this project")

    if infra_type != "cluster":
        raise ValueError(f"Unsupported infra type '{infra_type}' for /infra/create")

    infra_name = infra_config.get("name")
    if not infra_name:
        raise ValueError("infra_config 'name' is required")

    existing = db.fetch_all(
        "SELECT infra_name FROM Infra WHERE infra_name = ? AND project_id = ?",
        params=[infra_name, project_id],
    )
    if existing:
        raise ValueError("Infra already exists")

    resolved = _normalize_provisions(project_id, infra_name, infra_config, provisions)

    # Let each provisioner mutate infra_config (e.g. append NodePorts) before the
    # cluster is created — k3d port mappings are fixed at creation time.
    for entry in resolved:
        provisions_registry.get(entry["type"]).pre_cluster_create(infra_config, entry["config"])

    registry_use = _resolve_registry_for_cluster(project_id, infra_config)

    from infra.k3d import create_k3d_cluster
    create_k3d_cluster(infra_config, registry=registry_use)

    context = infra_config.get("context")
    if not context:
        raise ValueError("Cluster context not found after cluster creation")

    persisted: list[dict] = []
    for entry in resolved:
        module = provisions_registry.get(entry["type"])
        state = module.provision(context, infra_config, entry["config"])
        persisted.append({
            "type": entry["type"],
            "config": _strip_seed(entry["config"]),
            "state": state or {},
        })

    db.execute(
        """
        INSERT INTO Infra (project_id, infra_name, infra_type, infra_config, provisions)
        VALUES (?, ?, ?, ?, ?)
        """,
        params=[
            project_id,
            infra_name,
            infra_type,
            json.dumps(infra_config),
            json.dumps(persisted),
        ],
    )


def _delete_infra(user_id: int, project_id: int, infra_id: int):
    if not user_has_project_access(user_id, project_id):
        raise ValueError("User does not have access to this project")

    rows = db.fetch_all(
        """
        SELECT infra_name, infra_type, infra_config, provisions
        FROM Infra
        WHERE infra_id = ? AND project_id = ?
        """,
        params=[infra_id, project_id],
    )
    if not rows:
        raise ValueError("Infra not found")

    infra_name, infra_type, raw_infra_config, raw_provisions = rows[0]
    try:
        infra_config = json.loads(raw_infra_config)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Stored infra config is invalid") from exc
    try:
        persisted = json.loads(raw_provisions) if raw_provisions else []
    except (TypeError, json.JSONDecodeError):
        persisted = []

    if infra_type != "cluster":
        raise ValueError(f"Unsupported infra type '{infra_type}' for /infra/delete")

    context = infra_config.get("context")
    for entry in reversed(persisted):
        p_type = entry.get("type")
        if not p_type or not provisions_registry.has(p_type):
            continue
        try:
            provisions_registry.get(p_type).deprovision(
                context, infra_config, entry.get("config") or {}, entry.get("state") or {}
            )
        except Exception as exc:
            print(f"warning: deprovision '{p_type}' failed for infra_id={infra_id}: {exc}")

    from infra.k3d import delete_k3d_cluster
    cluster_name = _resolve_cluster_name(infra_name, infra_config)
    delete_k3d_cluster(cluster_name)

    db.execute(
        "DELETE FROM Infra WHERE infra_id = ? AND project_id = ?",
        params=[infra_id, project_id],
    )


def _fetch_infras(user_id: int, project_id: int):
    if not user_has_project_access(user_id, project_id):
        raise ValueError("User does not have access to this project")

    try:
        reconcile_provisions(project_id=project_id)
    except Exception as exc:
        print(f"warning: provision reconciliation failed for project_id={project_id}: {exc}")

    rows = db.fetch_all(
        """
        SELECT infra_id, infra_type, infra_config, provisions
        FROM Infra
        WHERE project_id = ?
        """,
        params=[project_id],
    )

    infras = []
    for infra_id, infra_type, raw_config, raw_provisions in rows:
        config_dict = json.loads(raw_config)
        try:
            persisted = json.loads(raw_provisions) if raw_provisions else []
        except (TypeError, json.JSONDecodeError):
            persisted = []

        context = config_dict.get("context")
        cluster_status = (
            k8s.get_cluster_status(context)
            if infra_type == "cluster" and context
            else {}
        )

        provision_views = []
        for entry in persisted:
            p_type = entry.get("type")
            if not p_type or not provisions_registry.has(p_type):
                provision_views.append({**entry, "status": {"error": "unknown provision type"}})
                continue
            module = provisions_registry.get(p_type)
            try:
                p_status = module.get_status(context, entry.get("config") or {}, entry.get("state") or {})
            except Exception as exc:
                p_status = {"error": str(exc)}
            provision_views.append({
                "type": p_type,
                "config": entry.get("config") or {},
                "state": entry.get("state") or {},
                "status": p_status,
            })

        infras.append({
            "infra_id": infra_id,
            "infra_type": infra_type,
            "infra_config": config_dict,
            "provisions": provision_views,
            "status": cluster_status,
        })

    return {"infras": infras}


def _get_kubeconfig(user_id: int, project_id: int, infra_id: int):
    if not user_has_project_access(user_id, project_id):
        raise ValueError("User does not have access to this project")

    rows = db.fetch_all(
        """
        SELECT infra_config
        FROM Infra
        WHERE infra_id = ? AND project_id = ?
        """,
        params=[infra_id, project_id],
    )
    if not rows:
        raise ValueError("Infra not found")

    infra_config = json.loads(rows[0][0])
    context = infra_config.get("context")
    if not context:
        raise ValueError("Infra kube context not found")
    try:
        kubeconfig_content = k8s.get_raw_kubeconfig(context, rewrite_host="localhost")
    except Exception as exc:
        raise ValueError(f"Failed to load kubeconfig: {exc}") from exc

    return {"kubeconfig": kubeconfig_content}


def reconcile_provisions(project_id: int | None = None) -> dict:
    where_clause = "infra_type = ?"
    params: list = ["cluster"]
    if project_id is not None:
        where_clause += " AND project_id = ?"
        params.append(project_id)

    rows = db.fetch_all(
        f"""
        SELECT infra_id, project_id, infra_name, infra_config, provisions
        FROM Infra
        WHERE {where_clause}
        """,
        params=params,
    )

    reconciled = 0
    updated = 0
    errors = 0

    for infra_id, row_project_id, infra_name, raw_config, raw_provisions in rows:
        try:
            infra_config = json.loads(raw_config)
        except (TypeError, json.JSONDecodeError):
            errors += 1
            continue
        try:
            persisted = json.loads(raw_provisions) if raw_provisions else []
        except (TypeError, json.JSONDecodeError):
            persisted = []

        if not persisted:
            continue

        reconciled += 1
        context = infra_config.get("context") or ""
        changed = False
        for entry in persisted:
            p_type = entry.get("type")
            if not p_type or not provisions_registry.has(p_type):
                continue
            module = provisions_registry.get(p_type)
            cfg = dict(entry.get("config") or {})
            state = entry.get("state") or {}
            try:
                new_state = module.reconcile(
                    infra_id=infra_id,
                    project_id=row_project_id,
                    infra_name=infra_name,
                    context=context,
                    infra_config=infra_config,
                    provision_config=cfg,
                    provision_state=state,
                )
            except Exception as exc:
                print(f"warning: reconcile '{p_type}' failed for infra_id={infra_id}: {exc}")
                errors += 1
                continue
            if new_state is not None:
                entry["state"] = new_state
                changed = True

        if changed:
            db.execute(
                "UPDATE Infra SET provisions = ? WHERE infra_id = ?",
                params=[json.dumps(persisted), infra_id],
            )
            updated += 1

    return {"reconciled": reconciled, "updated": updated, "errors": errors}
