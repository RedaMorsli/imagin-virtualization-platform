class_name ItemManagementView
extends VBoxContainer


signal item_pressed(item_card: ItemCard)
signal new_item_requested()

@export_category("Fetch")
@export var fetch_route: String
@export var include_project_id: bool = true

@export_category("Texts")
@export var search_message: String
@export var empty_message: String
@export var new_item_message: String

@onready var item_container: Container = %ItemContainer
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var empty_label: Label = %EmptyLabel
@onready var error_label: Label = %ErrorLabel
@onready var search_edit: LineEdit = %SearchEdit
@onready var new_item_button: Button = %NewItemButton


func _ready() -> void:
	search_edit.placeholder_text = search_message
	empty_label.text = empty_message
	new_item_button.text = new_item_message


func fetch():
	var response = await Http.send_request(
		API.api_url + fetch_route,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_GET,
		{'project_id': Context.project.project_id} if include_project_id else {},
		"Failed to fetch items"
	)
	if not response.is_successful():
		printerr("Couldn't fetch items")
		error_label.text = str(response.get_error())
		error_label.show()
		loading_spinner.hide()
		empty_label.hide()
		return
		
	for child in item_container.get_children():
		child.queue_free()
	
	var items = instanciate_items(response.get_data())
	
	loading_spinner.hide()
	item_container.visible = not items.is_empty()
	empty_label.visible = items.is_empty()
	error_label.hide()
	
	for item in items:
		item.item_pressed.connect(_on_item_pressed)
		item_container.add_child(item)


# Override to instanciate specific items
func instanciate_items(fetched_data) -> Array[ItemCard]:
	return []


func _on_item_pressed(item_card: ItemCard):
	item_pressed.emit(item_card)


func _on_new_item_button_pressed() -> void:
	new_item_requested.emit()


func _on_search_edit_text_changed(new_text: String) -> void:
	for item: ItemCard in item_container.get_children():
		if new_text.is_empty():
			item.show()
			continue
		item.visible = item.title.to_lower().strip_edges().contains(new_text.to_lower().strip_edges())
