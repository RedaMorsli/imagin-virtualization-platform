extends Control


const MAIN_SCENE = preload("uid://v8pl058l81vh")


func _ready() -> void:
	Auth.logged_in.connect(
		func ():
			get_tree().change_scene_to_packed(MAIN_SCENE)
	)
