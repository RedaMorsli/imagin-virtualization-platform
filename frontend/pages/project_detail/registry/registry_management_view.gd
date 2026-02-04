extends ItemManagementView

const NewRegistryDialogScene = preload("uid://dtnaw4i02hsbv")
const RegistryCardScene = preload("uid://jo6qcamyrf7w")


func instanciate_items(fetched_data) -> Array[ItemCard]:
	var registries = fetched_data['registries']
	var items: Array[ItemCard]
	Context.registries.clear()
	for r in registries:
		var registry: Infra = Infra.new.callv(r.values())
		Context.registries.append(registry)
		var item: ItemCard = ItemCard.instanciate()
		item.title = registry.infra_config.name
		item.item = registry
		items.append(item)
	return items


func _on_registry_pressed(item_card: ItemCard):
	pass


func _on_new_registry_requested() -> void:
	var dialog: DialogScene = NewRegistryDialogScene.instantiate()
	dialog.completed.connect(fetch)
	Dialog.popup(dialog)
