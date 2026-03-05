extends DialogScene


@onready var create_button: Button = %CreateButton
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var name_edit: LineEdit = %NameEdit
@onready var port_edit: SpinBox = %PortEdit



func _on_create_button_pressed() -> void:
	create_button.hide()
	loading_spinner.show()
	var data = {
		'project_id': Context.project.project_id,
		'infra_type': "registry",
		'infra_config': {
			'name': name_edit.text,
			'port': int(port_edit.value)
		}
	}
	var response = await Http.send_request(
		API.create_registry_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_POST,
		data,
		"Failed to create project"
	)
	if response.is_successful():
		completed.emit()
		queue_free()
	else:
		OS.alert("Error: " + response.get_error())
		create_button.show()
		loading_spinner.hide()
		return
