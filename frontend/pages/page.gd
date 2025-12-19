class_name Page
extends Control


func push_page(page_uid):
	var pack: PackedScene = load(page_uid)
	var new_page: Page = pack.instantiate()
	get_parent().add_child(new_page)
	new_page.set_current()


func pop_page():
	if get_parent().get_child_count() <= 1:
		print("Can't popback: only one page on the stack.")
		return
	var last_child: Node = get_parent().get_child(get_parent().get_child_count() - 1)
	var before_last_child: Node = get_parent().get_child(get_parent().get_child_count() - 2)
	before_last_child.show()
	last_child.queue_free()


func set_current():
	for child in get_parent().get_children():
		child.visible = child == self
