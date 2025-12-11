extends CanvasLayer


@onready var title: Label = %Title
@onready var dialog_container: MarginContainer = %DialogContainer


var _dialog_scene: DialogScene


func _ready() -> void:
	hide()


func popup(p_title: String, p_scene: PackedScene) -> DialogScene:
	title.text = p_title
	_dialog_scene = p_scene.instantiate()
	_dialog_scene.tree_exiting.connect(
		func ():
			hide()
	)
	dialog_container.add_child(_dialog_scene)
	show()
	return _dialog_scene


func _on_background_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.is_pressed():
		hide()
		_dialog_scene.queue_free()
