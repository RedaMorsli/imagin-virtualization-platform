class_name API
extends Script


const HEADERS_JSON = ["Content-Type: application/json"]
const ENV_API_URL = "API_URL"


static var api_url = "http://127.0.0.1:8000/" # Replaced by env var
static var login_url: String = api_url + "auth/login"
static var verify_url: String = api_url + "auth/verify"
static var create_project_url: String = api_url + "projects/create"
static var fetch_projects_url: String = api_url + "projects/fetch"


func _init() -> void:
	if OS.has_environment(ENV_API_URL):
		api_url = OS.get_environment(ENV_API_URL)
