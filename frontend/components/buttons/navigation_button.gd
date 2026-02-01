class_name NavigationButton
extends Button

# When the nav button is pressed, show the selected node and hide all other siblings
@export var nav_container: Container
#@export var title: String


func _ready() -> void:
	focus_mode = Control.FOCUS_NONE
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	pressed.connect(_on_nav_button_pressed)


func _on_nav_button_pressed():
	for child: CanvasItem in nav_container.get_parent().get_children():
		child.visible = child == nav_container
