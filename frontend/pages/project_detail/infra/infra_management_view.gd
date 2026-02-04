extends ItemManagementView


const NewInfraDialogScene = preload("uid://d0vx2n1uumtnt")
const ClusterCardScene = preload("uid://jo6qcamyrf7w")


func instanciate_items(fetched_data) -> Array[ItemCard]:
	var infras = fetched_data['infras']
	var items: Array[ItemCard]
	for i in infras:
		var infra: Infra = Infra.new.callv(i.values())
		var item: ClusterCard = ClusterCardScene.instantiate()
		item.item = infra
		items.append(item)
	return items


func _on_infra_pressed(item_card: ItemCard):
	pass


func _on_new_infra_requested() -> void:
	var dialog = Dialog.popup(NewInfraDialogScene.instantiate())
	dialog.completed.connect(fetch)
