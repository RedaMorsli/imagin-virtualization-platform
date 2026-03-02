extends DialogScene


@onready var project_name_edit: LineEdit = %ProjectNameEdit
@onready var create_button: Button = %CreateButton
@onready var loading_spinner: TextureRect = %LoadingSpinner


func _on_create_button_pressed() -> void:
	create_button.hide()
	loading_spinner.show()
	var data = {
		"project_name": project_name_edit.text,
	}
	var response = await Http.send_request(
		API.create_project_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_POST,
		data,
		"Failed to create project"
	)
	if response.is_successful():
		var response_data = response.get_data()
		completed.emit()
		queue_free()
	else:
		create_button.show()
		loading_spinner.hide()
		return
