class_name Infra
extends Resource


@export var infra_id: int

@export var infra_type: String

@export var infra_config: Dictionary


func _init(id: int, type: String, config: String) -> void:
	infra_id = id
	infra_type = type
	infra_config = JSON.parse_string(config)
