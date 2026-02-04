extends VBoxContainer


@export var dialog: DialogScene

@onready var create_button: Button = %FlowerCreateButton
@onready var infra_config_form: InfraConfigForm = %FlowerInfraConfigForm
@onready var servers: SpinBox = %FlowerServers
@onready var clients: SpinBox = %FlowerClients
@onready var cpu_limit: SpinBox = %FlowerCpuLimit
@onready var memory_limit: SpinBox = %FlowerMemoryLimit
@onready var loading_spinner: TextureRect = %FlowerLoadingSpinner
@onready var buttons: HBoxContainer = %FlowerButtons


func _on_create_button_pressed() -> void:
	buttons.hide()
	loading_spinner.show()
	var data = infra_config_form.get_data()
	data['provision'] = {
		'name': "flower",
		'servers': servers.value,
		'clients': clients.value,
		'client_resources': {
			'cpu': str(cpu_limit.value) + 'm',
			'memory': str(memory_limit.value) + 'Mi'
		}
	}
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
		return
	dialog.completed.emit()
	dialog.queue_free()
