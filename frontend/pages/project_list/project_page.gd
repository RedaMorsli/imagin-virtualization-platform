extends Page


const NewProjectDialogScene = preload("uid://dcdyc3esl7los")

@onready var project_managment_view: ItemManagementView = %ItemManagmentView


func _ready() -> void:
	_fetch_projects()


func _on_new_project_button_pressed() -> void:
	var dialog = Dialog.popup(NewProjectDialogScene)
	dialog.completed.connect(_fetch_projects)


func _fetch_projects():
	project_managment_view.fetch()


func _on_item_managment_view_item_pressed(item_card: ItemCard) -> void:
	Context.project = item_card.item
	push_page(PageCatalog.project_detail, [item_card.item])
