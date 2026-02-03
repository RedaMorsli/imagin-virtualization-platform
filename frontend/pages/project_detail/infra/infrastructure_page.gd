extends Page


@onready var infra_management_view: ItemManagementView = %InfraManagementView


func _ready() -> void:
	Events.infra_created.connect(_fetch_infras)
	_fetch_infras()


func _fetch_infras():
	infra_management_view.fetch()


func _on_kubeconfig_button_pressed() -> void:
	pass
	#var response = await Http.send_request(
		#API.fetch_kubeconfig_url,
		#Auth.HTTP_HEADER,
		#HTTPClient.METHOD_GET,
		#{
			#'project_id': Context.project.project_id,
			#'infra_id': infra_container.get_children()[0].infra.infra_id
		#},
		#"Failed to fetch kubeconfig"
	#)
	#if not response.is_successful():
		#printerr("Error while fetching cluster config file")
		#return
	#DisplayServer.clipboard_set(response.get_data()['kubeconfig'])
