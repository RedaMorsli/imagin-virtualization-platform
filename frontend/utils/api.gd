class_name API
extends Script


const HEADERS_JSON = ["Content-Type: application/json"]
const ENV_API_URL = "API_URL"


static var api_url = "http://localhost:8000/" # Replaced by env var
static var login_url: String = api_url + "auth/login"
static var verify_url: String = api_url + "auth/verify"
static var create_project_url: String = api_url + "projects/create"
static var fetch_projects_url: String = api_url + "projects/fetch"
static var create_infra_url: String = api_url + "infra/create"
static var fetch_infras_url: String = api_url + "infra/fetch"
static var fetch_kubeconfig_url: String = api_url + "infra/kubeconfig"
static var create_registry_url: String = api_url + "registry/create"
static var get_storage_status_url: String = api_url + "storage/status"
static var create_storage_url: String = api_url + "storage/create"


func _init() -> void:
	if OS.has_environment(ENV_API_URL):
		api_url = OS.get_environment(ENV_API_URL)
