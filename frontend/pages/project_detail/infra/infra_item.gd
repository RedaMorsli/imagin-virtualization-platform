extends PanelContainer

var infra: Infra

@onready var name_label: Label = %NameLabel


func _ready() -> void:
	if not infra:
		return
	name_label.text = infra.infra_config['name']
