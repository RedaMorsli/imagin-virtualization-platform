extends ItemManagementView


const NewExperimentDialog = preload("uid://cg6sftdi0e37l")


func instanciate_items(fetched_data) -> Array[ItemCard]:
	var experiments = fetched_data['experiments']
	var items: Array[ItemCard]
	for i in experiments:
		var exp: Infra = Experiment.new.callv(i.values())
		var item: ClusterCard = ClusterCard.instanciate()
		item.item = exp
		items.append(item)
	return items


func _on_new_item_requested() -> void:
	var dialog = Dialog.popup(NewExperimentDialog.instantiate())
	dialog.completed.connect(fetch)
