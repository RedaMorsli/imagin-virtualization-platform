extends DialogScene


@onready var http_request: HTTPRequest = %HTTPRequest
@onready var project_name_edit: LineEdit = %ProjectNameEdit
@onready var create_button: Button = %CreateButton
@onready var loading_spinner: TextureRect = %LoadingSpinner


func _on_create_button_pressed() -> void:
	create_button.hide()
	loading_spinner.show()
	var data = {
		"project_name": project_name_edit.text,
	}
	var json = JSON.stringify(data)
	var response = await Http.send_request(
		API.create_project_url,
		["Authorization: Bearer " + Config.auth_token],
		HTTPClient.METHOD_POST,
		json,
		"Failed to create project"
	)


func _on_http_request_request_completed(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code != HTTPClient.RESPONSE_OK:
		#Error.handle_http_error("Failed to create project", result, response_code)
		create_button.show()
		loading_spinner.hide()
		return
	var data = JSON.parse_string(body.get_string_from_utf8())
	completed.emit()
	queue_free()
