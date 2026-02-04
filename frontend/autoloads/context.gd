extends Node


var project: Project

var registries: Array[Infra]


func get_registry_id_by_name(reg_name: String):
	for reg in registries:
		if reg.infra_config.name == reg_name:
			return reg.infra_id
	return null
