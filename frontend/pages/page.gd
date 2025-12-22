class_name Page
extends Control


@export var title: String
@export var icon: Texture

var args: Array


func push_page(page_uid, args = []):
	var pack: PackedScene = load(page_uid)
	var new_page: Page = pack.instantiate()
	new_page.args = args
	get_parent().add_child(new_page)
	new_page.set_current()


func pop_back():
	if not visible:
		print("Can't pop back: this page is not the active one.")
	if get_parent().get_child_count() <= 1:
		print("Can't pop back: only one page on the stack.")
		return
	var last_child: Node = get_parent().get_child(get_parent().get_child_count() - 1)
	var before_last_child: Node = get_parent().get_child(get_parent().get_child_count() - 2)
	before_last_child.show()
	last_child.queue_free()


func set_current():
	for child in get_parent().get_children():
		child.visible = child == self


func pop_to_this_page():
	var pages = get_parent().get_children() as Array[Page]
	if self not in pages:
		printerr('Failed to pop to page: page not in root container')
		return
	pages.reverse()
	for page in pages:
		if page != self:
			page.pop_back()
		else:
			break
