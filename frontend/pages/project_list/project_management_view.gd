extends ItemManagementView


func instanciate_items(fetched_data) -> Array[ItemCard]:
	var projects = fetched_data['projects']
	var items: Array[ItemCard]
	for project in projects:
		var item: ItemCard = ItemCard.instanciate()
		item.item = Project.new(project.project_id, project.project_name, "Empty Project")
		item.title = project.project_name
		items.append(item)
	return items
