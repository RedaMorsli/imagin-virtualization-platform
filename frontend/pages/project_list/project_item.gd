class_name ProjectItem
extends PanelContainer


signal project_pressed(project: Project)

var project: Project

@onready var name_label: Label = %NameLabel
@onready var description_label: Label = %DescriptionLabel


func _ready() -> void:
	if project:
		name_label.text = project.project_name
		description_label.text = project.project_description


func _on_card_button_pressed() -> void:
	project_pressed.emit(project)
