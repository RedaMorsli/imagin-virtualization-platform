extends Page


var project: Project


func _ready() -> void:
	if not args.is_empty() and args[0] is Project:
		project = args[0]
	else:
		printerr("Project not found in project detail page")
		return
	
	title = project.project_name


func _on_back_button_pressed() -> void:
	pop_back()
