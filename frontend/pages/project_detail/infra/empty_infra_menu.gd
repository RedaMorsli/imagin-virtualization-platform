extends VBoxContainer


signal infra_created()


@onready var buttons: HBoxContainer = %Buttons
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var infra_config_form: InfraConfigForm = %InfraConfigForm


func _on_create_button_pressed() -> void:
	buttons.hide()
	loading_spinner.show()
	var data = infra_config_form.get_data()
	var response = await Http.send_request(
		API.create_infra_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_POST,
		data,
		'Failed to create cluster'
	)
	if response.is_successful():
		Events.infra_created.emit()
	else:
		buttons.show()
		loading_spinner.hide()
