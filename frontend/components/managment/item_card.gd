class_name ItemCard
extends PanelContainer


const _SCENE = preload("uid://becyat4dcn7ka")

signal item_pressed(item: ItemCard)
signal menu_option_pressed(idx: int)

@export var menu_options: Array[String]

var title: String
var item

@onready var title_label: Label = %TitleLabel
@onready var menu_button: MenuButton = %MenuButton


func _ready() -> void:
	title_label.text = title
	menu_button.get_popup().index_pressed.connect(_on_menu_option_pressed)
	for option in menu_options:
		menu_button.get_popup().add_item(option)
	menu_button.visible = not menu_options.is_empty()


static func instanciate() -> ItemCard:
	return _SCENE.instantiate()


func _on_card_button_pressed() -> void:
	item_pressed.emit(self)


func _on_menu_option_pressed(idx: int):
	menu_option_pressed.emit(idx)
