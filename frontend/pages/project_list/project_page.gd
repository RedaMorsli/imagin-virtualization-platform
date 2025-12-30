extends Page


const NewProjectDialogScene = preload("uid://dcdyc3esl7los")
const ProjectItemScene = preload("uid://becyat4dcn7ka")

@onready var fetch_http_request: HTTPRequest = %FetchHTTPRequest
@onready var project_container: GridContainer = %ProjectContainer
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var empty_label: Label = %EmptyLabel

var projects: = []


func _ready() -> void:
	_fetch_projects()


func _on_new_project_button_pressed() -> void:
	var dialog = Dialog.popup(NewProjectDialogScene)
	dialog.completed.connect(_fetch_projects)


func _fetch_projects():
	var response = await Http.send_request(
		API.fetch_projects_url,
		["Authorization: Bearer " + Config.auth_token],
		HTTPClient.METHOD_GET,
		"Failed to fetch projects"
	)
	projects = response.get_data()['projects']
	for child in project_container.get_children():
		child.queue_free()
	if not projects:
		loading_spinner.hide()
		empty_label.show()
		return
	for project in projects:
		var item: ProjectItem = ProjectItemScene.instantiate()
		item.project = Project.new(project.project_id, project.project_name, "Empty Project")
		item.project_pressed.connect(_on_project_pressed)
		project_container.add_child(item)
	loading_spinner.hide()
	project_container.visible = not projects.is_empty()
	empty_label.visible = projects.is_empty()


func _on_project_pressed(project: Project):
	push_page(PageCatalog.project_detail, [project])
