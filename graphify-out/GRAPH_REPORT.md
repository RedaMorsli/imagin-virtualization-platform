# Graph Report - .  (2026-04-29)

## Corpus Check
- Corpus is ~15,829 words - fits in a single context window. You may not need a graph.

## Summary
- 412 nodes · 625 edges · 33 communities detected
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 45 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_FL Experiment Lifecycle|FL Experiment Lifecycle]]
- [[_COMMUNITY_DuckDB Schema & Migrations|DuckDB Schema & Migrations]]
- [[_COMMUNITY_Project Docs & Architecture|Project Docs & Architecture]]
- [[_COMMUNITY_Backend Startup & FL Glue|Backend Startup & FL Glue]]
- [[_COMMUNITY_Flower Sample Strategy Internals|Flower Sample Strategy Internals]]
- [[_COMMUNITY_Cluster CRUD API|Cluster CRUD API]]
- [[_COMMUNITY_Flower-on-K8s Provisioning|Flower-on-K8s Provisioning]]
- [[_COMMUNITY_Per-run FL Docker Topology|Per-run FL Docker Topology]]
- [[_COMMUNITY_FL Server Reporting Hooks|FL Server Reporting Hooks]]
- [[_COMMUNITY_free5gc 5G Core Provision|free5gc 5G Core Provision]]
- [[_COMMUNITY_API Routing & App Wiring|API Routing & App Wiring]]
- [[_COMMUNITY_FL Client Training Logic|FL Client Training Logic]]
- [[_COMMUNITY_Docker Container Helpers|Docker Container Helpers]]
- [[_COMMUNITY_MinIO Object Storage|MinIO Object Storage]]
- [[_COMMUNITY_Auth Login & Tokens|Auth Login & Tokens]]
- [[_COMMUNITY_Traefik Dynamic Routing|Traefik Dynamic Routing]]
- [[_COMMUNITY_Auth AST Internals|Auth AST Internals]]
- [[_COMMUNITY_Headlamp K8s Dashboard|Headlamp K8s Dashboard]]
- [[_COMMUNITY_DuckDB Query Helpers|DuckDB Query Helpers]]
- [[_COMMUNITY_Project & Template Endpoints|Project & Template Endpoints]]
- [[_COMMUNITY_MNIST Data Loader|MNIST Data Loader]]
- [[_COMMUNITY_get_container_status (orphan)|get_container_status (orphan)]]
- [[_COMMUNITY_remove_container (orphan)|remove_container (orphan)]]
- [[_COMMUNITY_check_port_available (orphan)|check_port_available (orphan)]]
- [[_COMMUNITY_pause_clients (orphan)|pause_clients (orphan)]]
- [[_COMMUNITY_unpause_clients (orphan)|unpause_clients (orphan)]]
- [[_COMMUNITY_get_run_container_status (orphan)|get_run_container_status (orphan)]]
- [[_COMMUNITY_create_k3d_registry (orphan)|create_k3d_registry (orphan)]]
- [[_COMMUNITY_get_registry_status (orphan)|get_registry_status (orphan)]]
- [[_COMMUNITY_get_cluster_status (orphan)|get_cluster_status (orphan)]]
- [[_COMMUNITY_MinIO health_check (orphan)|MinIO health_check (orphan)]]
- [[_COMMUNITY_free5gc.get_status (orphan)|free5gc.get_status (orphan)]]
- [[_COMMUNITY_headlamp.get_status (orphan)|headlamp.get_status (orphan)]]

## God Nodes (most connected - your core abstractions)
1. `user_has_project_access()` - 13 edges
2. `_load_kube_config()` - 11 edges
3. `infra._create_infra` - 11 edges
4. `free5gc.provision` - 10 edges
5. `ReportingFedAvg` - 8 edges
6. `FastAPI app (main.py)` - 8 edges
7. `Infra table (with provisions JSON column)` - 8 edges
8. `launch_run (FL Docker)` - 8 edges
9. `_create_infra()` - 7 edges
10. `teardown_run()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `free5gc.provision` --references--> `gtp5g kernel module`  [EXTRACTED]
  backend/infra/provisions/free5gc.py → README.md
- `startup_tasks()` --calls--> `init_db()`  [INFERRED]
  main.py → db.py
- `_create_infra()` --calls--> `user_has_project_access()`  [INFERRED]
  api\infra.py → api\project.py
- `_delete_infra()` --calls--> `user_has_project_access()`  [INFERRED]
  api\infra.py → api\project.py
- `_fetch_infras()` --calls--> `user_has_project_access()`  [INFERRED]
  api\infra.py → api\project.py

## Hyperedges (group relationships)
- **FL run launch + reporting pipeline** — experiment_launch_run_endpoint, infra_fl_docker, fl_server_module, fl_client_module, experiment_run_metrics_endpoint, experiment_run_complete_endpoint [EXTRACTED 0.90]
- **Client selection + container pause/unpause loop** — fl_server_reporting_fedavg, fl_server_manage_clients, experiment_manage_clients_endpoint, infra_fl_docker [EXTRACTED 0.90]
- **Infra provisions lifecycle (create/reconcile/delete)** — infra_create, infra_delete, infra_reconcile_provisions, infra_provisions_registry, db_infra_table, provisions_array_concept [EXTRACTED 0.95]
- **Provision lifecycle protocol (pre_cluster_create/provision/deprovision/get_status/reconcile)** — headlamp_provision, free5gc_provision, provisions_array_concept, infra_provisions_registry [EXTRACTED 0.95]
- **Cluster web UI exposure (k8s install + Traefik route + path-based base URL)** — k8s_install_headlamp, traefik_register_endpoint, headlamp_provision, cluster_webui_exposure_pattern [EXTRACTED 0.90]
- **Per-run FL Docker topology (server+clients+isolated network+platform bridge)** — fl_docker_launch_run, fl_docker_per_run_network_concept, fl_docker_worker_image_concept, fl_server_module, fl_client_module [EXTRACTED 0.90]

## Communities

### Community 0 - "FL Experiment Lifecycle"
Cohesion: 0.06
Nodes (48): _create_experiment(), create_experiment_endpoint(), _create_run(), CreateExperimentRequest, _delete_experiment(), delete_experiment_endpoint(), DeleteExperimentRequest, _fetch_experiments() (+40 more)

### Community 1 - "DuckDB Schema & Migrations"
Cohesion: 0.07
Nodes (38): db.get_seq_last_val, Infra table (with provisions JSON column), db.init_db, db._migrate_infra_provisions_column, ProjectUsers table, Projects table, experiment._create_experiment, free5gc.deprovision (+30 more)

### Community 2 - "Project Docs & Architecture"
Cohesion: 0.08
Nodes (33): API route template pattern (SCHEMAS->ENDPOINTS->LOGIC), Cluster web UI exposure flow (k8s+traefik), context.md (project context), Docker Compose 3-service architecture (traefik+backend+frontend), DuckDB file-based database, provision_flower_on_cluster, Flower SuperLink/SuperNode/SuperExec architecture, _ensure_multus_installed (+25 more)

### Community 3 - "Backend Startup & FL Glue"
Cohesion: 0.09
Nodes (31): startup_tasks(), Client selection (algorithm + container pause), create_docker_container, ExperimentRuns table, Experiments table, RunMetrics table, experiment._background_launch, experiment._create_run (+23 more)

### Community 4 - "Flower Sample Strategy Internals"
Cohesion: 0.11
Nodes (21): FedAvg, build_server_eval_fn(), build_strategy(), evaluate(), FlowerClient, get_weights(), load_datasets(), main() (+13 more)

### Community 5 - "Cluster CRUD API"
Cohesion: 0.12
Nodes (24): _create_infra(), create_infra_endpoint(), _delete_infra(), delete_infra_endpoint(), _fetch_infras(), fetch_infras_endpoint(), fetch_kubeconfig_endpoint(), FetchInfraRequest (+16 more)

### Community 6 - "Flower-on-K8s Provisioning"
Cohesion: 0.22
Nodes (17): provision_flower_on_cluster(), apply_manifest(), apply_manifest_from_url(), _build_probe_http_get_patch(), change_service_type(), configure_headlamp_base_url(), _configured_kube_api_rewrite_host(), create_headlamp_service_account_token() (+9 more)

### Community 7 - "Per-run FL Docker Topology"
Cohesion: 0.19
Nodes (17): _client_name(), ensure_worker_image(), get_run_container_status(), launch_run(), _net_name(), pause_clients(), FL Docker — manages per-run Flower containers.  Each run gets:   - An isolated D, Force-remove all containers and the network for a run. (+9 more)

### Community 8 - "FL Server Reporting Hooks"
Cohesion: 0.2
Nodes (9): _manage_clients(), _post(), FL Server — runs inside a Docker container, one per FL run.  Environment variabl, Call the platform backend to pause or unpause client containers., FedAvg with per-round client selection, metrics reporting, and container managem, Return sorted list of selected client indices for this round., ReportingFedAvg, select_clients() (+1 more)

### Community 9 - "free5gc 5G Core Provision"
Cohesion: 0.26
Nodes (12): deprovision(), _ensure_helm_repo(), _ensure_multus_installed(), _helm_install(), _helm_uninstall(), pre_cluster_create(), provision(), free5gc + UERANSIM + web console provisioner.  Deploys the towards5gs Helm chart (+4 more)

### Community 10 - "API Routing & App Wiring"
Cohesion: 0.15
Nodes (14): Auth router (/auth), Backend requirements (fastapi, duckdb, minio, ...), Experiment router (/experiments), Infra router (/infra), FastAPI app (main.py), main.start_auth_server, delete_object, ensure_bucket (+6 more)

### Community 11 - "FL Client Training Logic"
Cohesion: 0.24
Nodes (6): get_weights(), load_data(), MNISTClient, MNISTModel, FL Client — runs inside a Docker container, one per simulated client.  Trains a, set_weights()

### Community 12 - "Docker Container Helpers"
Cohesion: 0.22
Nodes (11): check_port_available(), _coerce_port_int(), _coerce_port_value(), create_docker_container(), get_container_status(), _is_port_available(), _normalize_ports(), _normalize_volumes() (+3 more)

### Community 13 - "MinIO Object Storage"
Cohesion: 0.23
Nodes (12): delete_object(), ensure_bucket(), _get_client(), _get_endpoint(), health_check(), list_bucket_objects(), Check if the MinIO instance is ready to accept requests.      Hits the MinIO rea, Create the bucket if it does not already exist. (+4 more)

### Community 14 - "Auth Login & Tokens"
Cohesion: 0.19
Nodes (13): auth._generate_token, auth.get_token, auth.get_user_by_token, auth._login, auth.login_endpoint, auth.verify_endpoint, auth._verify_token, DuckDB index.db file (+5 more)

### Community 15 - "Traefik Dynamic Routing"
Cohesion: 0.35
Nodes (11): _bounded_dns_label(), build_endpoint_id(), delete_http_endpoint(), register_http_endpoint(), _resolve_domain_name(), _resolve_dynamic_dir(), resolve_endpoint_details(), _resolve_endpoint_path_base() (+3 more)

### Community 16 - "Auth AST Internals"
Cohesion: 0.29
Nodes (9): _generate_token(), get_token(), _login(), login_endpoint(), LoginRequest, LoginResponse, verify_endpoint(), _verify_token() (+1 more)

### Community 17 - "Headlamp K8s Dashboard"
Cohesion: 0.39
Nodes (7): deprovision(), pre_cluster_create(), provision(), Headlamp web UI provisioner.  Installs the upstream Headlamp manifest into the c, reconcile(), _resolve_port(), _seed_endpoint_id()

### Community 18 - "DuckDB Query Helpers"
Cohesion: 0.54
Nodes (7): execute(), execute_sql_file(), fetch_all(), get_seq_current_val(), get_seq_last_val(), init_db(), _migrate_infra_provisions_column()

### Community 19 - "Project & Template Endpoints"
Cohesion: 0.48
Nodes (6): create_project_endpoint(), _get_function(), new_endpoint(), NewRequest, NewResponse, _post_function()

### Community 21 - "MNIST Data Loader"
Cohesion: 0.67
Nodes (3): load_data (IID MNIST shard), MNISTClient (NumPyClient), MNISTModel CNN

### Community 22 - "get_container_status (orphan)"
Cohesion: 1.0
Nodes (1): get_container_status

### Community 23 - "remove_container (orphan)"
Cohesion: 1.0
Nodes (1): remove_container

### Community 24 - "check_port_available (orphan)"
Cohesion: 1.0
Nodes (1): check_port_available

### Community 25 - "pause_clients (orphan)"
Cohesion: 1.0
Nodes (1): pause_clients

### Community 26 - "unpause_clients (orphan)"
Cohesion: 1.0
Nodes (1): unpause_clients

### Community 27 - "get_run_container_status (orphan)"
Cohesion: 1.0
Nodes (1): get_run_container_status

### Community 28 - "create_k3d_registry (orphan)"
Cohesion: 1.0
Nodes (1): create_k3d_registry

### Community 29 - "get_registry_status (orphan)"
Cohesion: 1.0
Nodes (1): get_registry_status

### Community 30 - "get_cluster_status (orphan)"
Cohesion: 1.0
Nodes (1): get_cluster_status

### Community 31 - "MinIO health_check (orphan)"
Cohesion: 1.0
Nodes (1): MinIO health_check

### Community 32 - "free5gc.get_status (orphan)"
Cohesion: 1.0
Nodes (1): free5gc.get_status

### Community 33 - "headlamp.get_status (orphan)"
Cohesion: 1.0
Nodes (1): headlamp.get_status

## Knowledge Gaps
- **88 isolated node(s):** `Validate provision entries, attach the per-provision _seed, and inject a     leg`, `FL Client — runs inside a Docker container, one per simulated client.  Trains a`, `FL Server — runs inside a Docker container, one per FL run.  Environment variabl`, `Return sorted list of selected client indices for this round.`, `Call the platform backend to pause or unpause client containers.` (+83 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `get_container_status (orphan)`** (1 nodes): `get_container_status`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `remove_container (orphan)`** (1 nodes): `remove_container`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `check_port_available (orphan)`** (1 nodes): `check_port_available`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `pause_clients (orphan)`** (1 nodes): `pause_clients`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `unpause_clients (orphan)`** (1 nodes): `unpause_clients`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `get_run_container_status (orphan)`** (1 nodes): `get_run_container_status`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `create_k3d_registry (orphan)`** (1 nodes): `create_k3d_registry`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `get_registry_status (orphan)`** (1 nodes): `get_registry_status`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `get_cluster_status (orphan)`** (1 nodes): `get_cluster_status`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `MinIO health_check (orphan)`** (1 nodes): `MinIO health_check`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `free5gc.get_status (orphan)`** (1 nodes): `free5gc.get_status`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `headlamp.get_status (orphan)`** (1 nodes): `headlamp.get_status`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `infra.fl_docker (worker container manager)` connect `Backend Startup & FL Glue` to `FL Experiment Lifecycle`?**
  _High betweenness centrality (0.148) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `user_has_project_access()` (e.g. with `_create_experiment()` and `_delete_experiment()`) actually correct?**
  _`user_has_project_access()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `infra._create_infra` (e.g. with `headlamp.pre_cluster_create` and `free5gc.pre_cluster_create`) actually correct?**
  _`infra._create_infra` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Validate provision entries, attach the per-provision _seed, and inject a     leg`, `FL Client — runs inside a Docker container, one per simulated client.  Trains a`, `FL Server — runs inside a Docker container, one per FL run.  Environment variabl` to the rest of the system?**
  _88 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FL Experiment Lifecycle` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._
- **Should `DuckDB Schema & Migrations` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Project Docs & Architecture` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._