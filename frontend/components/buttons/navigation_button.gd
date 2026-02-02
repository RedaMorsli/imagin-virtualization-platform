class_name NavigationButton
extends Button

# When the nav button is pressed, show the selected node and hide all other siblings
@export var nav_container: Container
@export var press_on_ready: bool = false
#@export var title: String


func _ready() -> void:
	focus_mode = Control.FOCUS_NONE
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	pressed.connect(_on_nav_button_pressed)
	if press_on_ready:
		button_pressed = true
		pressed.emit()


func _on_nav_button_pressed():
	for child: CanvasItem in nav_container.get_parent().get_children():
		child.visible = child == nav_container
