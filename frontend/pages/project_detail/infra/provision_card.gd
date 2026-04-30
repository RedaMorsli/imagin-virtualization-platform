class_name ProvisionCard
extends PanelContainer


@export var icon: Texture
@export var title: String
@export var description: String
@export var type: String
@export var config: Dictionary[String, Variant]

@onready var icon_texture: TextureRect = %IconTexture
@onready var title_label: Label = %Title
@onready var description_label: Label = %Description


func _ready() -> void:
	icon_texture.texture = icon
	title_label.text = title
	description_label.text = description


func get_data() -> Dictionary:
	return {
		'type': type,
		'config': config
	}
