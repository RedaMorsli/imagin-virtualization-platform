extends Page


const NewRegistryDialog = preload("uid://dtnaw4i02hsbv")


func _on_new_button_pressed() -> void:
	Dialog.popup(NewRegistryDialog)
