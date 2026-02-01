extends VBoxContainer


signal infra_created()

@onready var infra_name: LineEdit = %EmptyInfraName
@onready var infra_type: OptionButton = %EmptyInfraType
@onready var node_count: SpinBox = %EmptyNodeCount
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var buttons: HBoxContainer = %Buttons


func _on_create_button_pressed() -> void:
	buttons.hide()
	loading_spinner.show()
	var data = {
		'project_id': Context.project.project_id,
		'infra_type': infra_type.text.to_lower(),
		'infra_config': {
			'name': infra_name.text,
			'node_count': node_count.value
		}
	}
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
