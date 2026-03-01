class_name InfraConfigForm
extends VBoxContainer

@onready var infra_name: LineEdit = %EmptyInfraName
@onready var infra_type: OptionButton = %EmptyInfraType
@onready var node_count: SpinBox = %EmptyNodeCount
@onready var registry_option: OptionButton = %RegistryOption
@onready var webui_check: CheckBox = %WebuiCheck
@onready var web_ui_port: SpinBox = %WebUIPort


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
			'web_ui': webui_check.button_pressed,
			'web_ui_port': web_ui_port.value
		}
	}
