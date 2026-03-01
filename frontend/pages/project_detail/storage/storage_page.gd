extends Page


@onready var error_label: Label = %ErrorLabel
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var not_active_container: VBoxContainer = %NotActiveContainer
@onready var active_container: VBoxContainer = %ActiveContainer


func _ready() -> void:
	loading_spinner.show()
	not_active_container.hide()
	active_container.hide()
	error_label.hide()
	var status = await _get_storage_status()
	match status:
		'active':
			not_active_container.hide()
			active_container.show()
		'disabled':
			not_active_container.show()
		_:
			error_label.text = str(status)
			error_label.show()
	loading_spinner.hide()


func _get_storage_status():
	var data = {
		'project_id': Context.project.project_id
	}
	var response = await Http.send_request(
		API.get_storage_status_url,
		["Authorization: Bearer " + Config.auth_token],
		HTTPClient.METHOD_GET,
		data,
		"Failed to get storage status"
	)
	if response.is_successful():
		return response.get_data().status
	else:
		return response.get_error()


func _enable_storage():
	var data = {
		'project_id': Context.project.project_id
	}
	var response = await Http.send_request(
		API.create_storage_url,
		["Authorization: Bearer " + Config.auth_token],
		HTTPClient.METHOD_POST,
		data,
		"Failed to create storage"
	)
	if response.is_successful():
		active_container.show()
		not_active_container.hide()
	else:
		error_label.text = response.get_error()
		error_label.show()
		not_active_container.show()
