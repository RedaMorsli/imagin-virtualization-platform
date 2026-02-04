extends ItemManagementView


const NewProjectDialogScene = preload("uid://dcdyc3esl7los")

@export var root_page: Page


func instanciate_items(fetched_data) -> Array[ItemCard]:
	var projects = fetched_data['projects']
	var items: Array[ItemCard]
	for project in projects:
		var item: ItemCard = ItemCard.instanciate()
		item.item = Project.new(project.project_id, project.project_name, "Empty Project")
		item.title = project.project_name
		items.append(item)
	return items


func _on_new_project_button_pressed() -> void:
	var dialog = Dialog.popup(NewProjectDialogScene.instantiate())
	dialog.completed.connect(fetch)


func _on_project_pressed(item_card: ItemCard) -> void:
	Context.project = item_card.item
	root_page.push_page(PageCatalog.project_detail, [item_card.item])
