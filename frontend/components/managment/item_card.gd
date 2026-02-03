class_name ItemCard
extends PanelContainer


const _SCENE = preload("uid://becyat4dcn7ka")

signal item_pressed(item: ItemCard)

@export var title: String

var item

@onready var title_label: Label = %TitleLabel


func _ready() -> void:
	title_label.text = title
	


static func instanciate() -> ItemCard:
	return _SCENE.instantiate()


func _on_card_button_pressed() -> void:
	item_pressed.emit(self)
