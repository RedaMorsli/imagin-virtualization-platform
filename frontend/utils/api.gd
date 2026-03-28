class_name API
extends Script


const HEADERS_JSON = ["Content-Type: application/json"]
const ENV_API_URL = "API_URL"
const WEB_API_PATH = "/api/"
const DEV_API_BASE = "http://localhost:8000/"


static var api_url: String:
	get:
		return _get_api_base()

static var login_url: String:
	get:
		return _build_url("auth/login")

static var verify_url: String:
	get:
		return _build_url("auth/verify")

static var create_project_url: String:
	get:
		return _build_url("projects/create")

static var fetch_projects_url: String:
	get:
		return _build_url("projects/fetch")

static var create_infra_url: String:
	get:
		return _build_url("infra/create")


static var delete_infra_url: String:
	get:
		return _build_url("infra/delete")

static var fetch_infras_url: String:
	get:
		return _build_url("infra/fetch")

static var fetch_kubeconfig_url: String:
	get:
		return _build_url("infra/kubeconfig")

static var create_registry_url: String:
	get:
		return _build_url("registry/create")

static var list_files_url: String:
	get:
		return _build_url("storage/files")

static var upload_file_url: String:
	get:
		return _build_url("storage/upload")

static var delete_file_url: String:
	get:
		return _build_url("storage/file")


static func _get_api_base() -> String:
	# In browser builds, route backend calls through the same origin reverse proxy.
	if OS.has_feature("web"):
		return _get_web_api_base()
	if OS.has_environment(ENV_API_URL):
		return _normalize_base_url(OS.get_environment(ENV_API_URL))
	return DEV_API_BASE


static func _build_url(path: String) -> String:
	return _get_api_base() + path


static func _normalize_base_url(url: String) -> String:
	var normalized = url.strip_edges()
	if normalized.is_empty():
		return DEV_API_BASE
	if not normalized.ends_with("/"):
		normalized += "/"
	return normalized


static func _get_web_api_base() -> String:
	if not Engine.has_singleton("JavaScriptBridge"):
		return DEV_API_BASE
	var js_bridge = Engine.get_singleton("JavaScriptBridge")
	var origin = js_bridge.eval("window.location.origin")
	var origin_text = str(origin).strip_edges()
	if origin_text.is_empty():
		return DEV_API_BASE
	if origin_text.ends_with("/"):
		origin_text = origin_text.left(origin_text.length() - 1)
	return origin_text + WEB_API_PATH
