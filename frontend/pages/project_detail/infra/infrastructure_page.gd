extends Page


const InfraItemScene = preload("uid://c5bygne2f7jso")

@onready var infra_container: GridContainer = %InfraContainer
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var empty_label: Label = %EmptyLabel
@onready var error_label: Label = %ErrorLabel


func _ready() -> void:
	Events.infra_created.connect(_fetch_infras)
	_fetch_infras()


func _fetch_infras():
	for child in infra_container.get_children():
		child.queue_free()
	loading_spinner.show()
	empty_label.hide()
	error_label.hide()
	
	var response = await Http.send_request(
		API.fetch_infras_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_GET,
		{'project_id': Context.project.project_id},
		"Failed to fetch infrastructures"
	)
	loading_spinner.hide()
	if not response.is_successful():
		printerr("Error while fetching infrastructures")
		error_label.text = response.get_error()
		error_label.show()
		return
	var infras = response.get_data()['infras']
	if not infras or infras.is_empty():
		empty_label.show()
		return
	for i: Dictionary in infras:
		var infra: Infra = Infra.new.callv(i.values())
		var item = InfraItemScene.instantiate()
		item.infra = infra
		infra_container.add_child(item)
	infra_container.show()
