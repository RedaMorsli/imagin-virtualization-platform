class_name Project
extends Resource


@export var project_id: int

@export var project_name: String

@export var project_description: String


func _init(id, name, description) -> void:
	project_id = id
	project_name = name
	project_description = description
