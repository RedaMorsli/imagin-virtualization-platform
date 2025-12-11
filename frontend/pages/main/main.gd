extends Control


const LOGIN_SCENE_FILE = "res://pages/auth/login_page.tscn"

@onready var user_button: Button = %UserButton


func _ready() -> void:
	user_button.text = Auth.user.username
	Auth.logged_out.connect(
		func ():
			get_tree().change_scene_to_file(LOGIN_SCENE_FILE)
	)


func _on_button_pressed() -> void:
	Auth.logout()
