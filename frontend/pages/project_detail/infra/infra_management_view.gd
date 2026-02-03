extends ItemManagementView


const NewInfraDialogScene = preload("uid://d0vx2n1uumtnt")


func instanciate_items(fetched_data) -> Array[ItemCard]:
	var infras = fetched_data['infras']
	var items: Array[ItemCard]
	for i in infras:
		var infra: Infra = Infra.new.callv(i.values())
		var item: ItemCard = ItemCard.instanciate()
		item.item = infra
		item.title = infra.infra_config.name
		items.append(item)
	return items


func _on_infra_pressed(item_card: ItemCard):
	pass


func _on_new_infra_requested() -> void:
	Dialog.popup(NewInfraDialogScene)
