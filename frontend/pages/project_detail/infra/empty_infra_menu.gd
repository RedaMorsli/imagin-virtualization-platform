extends Control


signal infra_created()

@export var dialog: DialogScene

@onready var buttons: HBoxContainer = %Buttons
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var infra_config_form: InfraConfigForm = %InfraConfigForm
@onready var error_label: Label = %ErrorLabel


func _on_create_button_pressed() -> void:
	buttons.hide()
	error_label.hide()
	loading_spinner.show()
	var data = infra_config_form.get_data()
	var response = await Http.send_request(
		API.create_infra_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_POST,
		data,
		'Failed to create cluster'
	)
	if not response.is_successful():
		buttons.show()
		loading_spinner.hide()
		error_label.text = response.get_error()
		error_label.show()
		return
	dialog.completed.emit()
	dialog.queue_free()
