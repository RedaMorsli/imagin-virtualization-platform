class_name Infra
extends Resource


@export var infra_id: int

@export var infra_type: String

@export var infra_config: Dictionary

@export var status: Dictionary

@export var provisions: Array


func _init(id: int, type: String, config, prov, stat) -> void:
	infra_id = id
	infra_type = type
	infra_config = config
	status = stat
	provisions = prov
	#infra_config = JSON.parse_string(config)
	#status = JSON.parse_string(stat)
