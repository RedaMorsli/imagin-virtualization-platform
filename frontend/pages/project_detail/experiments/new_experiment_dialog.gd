extends DialogScene


@onready var type_option: OptionButton = %TypeOption
@onready var name_edit: LineEdit = %NameEdit
@onready var create_button: Button = %CreateButton
@onready var loading_spinner: TextureRect = %LoadingSpinner


func _on_create_button_pressed() -> void:
	create_button.hide()
	loading_spinner.show()
	var data = {
		'project_id': Context.project.project_id,
		'experiment_type': "fl_flower",
		'experiment_config': {
			'name': name_edit.text
		}
	}
	var response = await Http.send_request(
		API.create_registry_url,
		["Authorization: Bearer " + Config.auth_token],
		HTTPClient.METHOD_POST,
		data,
		"Failed to create project"
	)
	if response.is_successful():
		completed.emit()
		queue_free()
	else:
		create_button.show()
		loading_spinner.hide()
		return
