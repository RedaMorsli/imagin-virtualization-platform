class_name Experiment
extends Resource


@export var experiment_id: int

@export var experiment_type: String

@export var experiment_config: Dictionary



func _init(id: int, type: String, config, stat) -> void:
	experiment_id = id
	experiment_type = type
	experiment_config = config
