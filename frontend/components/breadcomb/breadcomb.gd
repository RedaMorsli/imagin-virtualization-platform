class_name Breadcomb
extends HBoxContainer


@export var root: Container
@export var separator_texture: Texture


func _ready() -> void:
	if not root:
		return
	
	for child in root.get_children():
		if child is Page:
			_add_item(child)
	
	root.child_entered_tree.connect(_add_item)
	root.child_exiting_tree.connect(_remove_item)


func _add_item(page: Node):
	if not page.is_node_ready():
		await page.ready
	var item: Button = Button.new()
	item.text = page.title
	item.icon = page.icon
	item.flat = true
	item.theme_type_variation = "FlatButton"
	item.focus_mode = Control.FOCUS_NONE
	item.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	item.pressed.connect(page.pop_to_this_page)
	var separator = Button.new()
	separator.icon = separator_texture
	separator.flat = true
	separator.theme_type_variation = "FlatButton"
	separator.disabled = true
	item.set_meta('page', page)
	item.set_meta('separator', separator)
	if get_child_count() >= 1:
		add_child(separator)
	add_child(item)


func _remove_item(page: Node):
	var item: Node
	for child in get_children():
		if child.has_meta('page') and child.get_meta('page') == page:
			item = child
	if not item:
		printerr("Error while removing breadcomb item")
		return
	if item.has_meta('separator'):
		item.get_meta('separator').queue_free()
	item.queue_free()
