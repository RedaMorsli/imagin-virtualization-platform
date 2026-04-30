extends DialogScene

@onready var infra_name: LineEdit = %EmptyInfraName
@onready var infra_type: OptionButton = %EmptyInfraType
@onready var node_count: SpinBox = %EmptyNodeCount
@onready var registry_option: OptionButton = %RegistryOption
#@onready var webui_check: CheckBox = %WebuiCheck
#@onready var web_ui_port: SpinBox = %WebUIPort

@onready var buttons: HBoxContainer = %Buttons
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var error_label: Label = %ErrorLabel
@onready var provision_container: GridContainer = %ProvisionContainer


func _ready() -> void:
	for registry in Context.registries:
		registry_option.add_item(registry.infra_config.name)


func get_data() -> Dictionary:
	return {
		'project_id': Context.project.project_id,
		'infra_type': infra_type.text.to_lower(),
		'infra_config': {
			'name': infra_name.text,
			'node_count': node_count.value,
			'registry_infra_id': Context.get_registry_id_by_name(registry_option.text),
			#'web_ui': webui_check.button_pressed,
			#'web_ui_port': web_ui_port.value
		},
		'provisions': _get_provisions()
	}

func _get_provisions() -> Array:
	var provisions := []
	for provision: ProvisionCard in provision_container.get_children():
		provisions.append(provision.get_data())
	return provisions


func _on_create_button_pressed() -> void:
	buttons.hide()
	error_label.hide()
	loading_spinner.show()
	var data = get_data()
	var response = await Http.send_request(
		API.create_infra_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_POST,
		get_data(),
		'Failed to create cluster'
	)
	if not response.is_successful():
		buttons.show()
		loading_spinner.hide()
		error_label.text = response.get_error()
		error_label.show()
		return
	completed.emit()
	queue_free()
