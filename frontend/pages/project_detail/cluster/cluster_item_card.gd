class_name ClusterCard
extends ItemCard


@onready var status_label: Label = %StatusLabel
@onready var available_nodes_label: Label = %AvailableNodesLabel
@onready var total_nodes_label: Label = %TotalNodesLabel

var infra: Infra


func _ready() -> void:
	infra = item as Infra
	title = infra.infra_config.name
	var ready_nodes = int(infra.status['nodes_ready'])
	var total_nodes = int(infra.infra_config['node_count'])
	available_nodes_label.text = str(ready_nodes)
	total_nodes_label.text = str(total_nodes)
	if ready_nodes == 0:
		status_label.text = 'Stopped'
	elif ready_nodes < total_nodes:
		status_label.text = 'Partially running'
	elif ready_nodes == total_nodes:
		status_label.text = 'Running'
	else:
		status_label.text = 'Unkown Issue'
	super()


func _on_option_pressed(idx: int):
	match idx:
		0:
			var response = await Http.send_request(
				API.fetch_kubeconfig_url,
				Auth.HTTP_HEADER,
				HTTPClient.METHOD_GET,
				{
					'project_id': Context.project.project_id,
					'infra_id': infra.infra_id
				},
				"Failed to fetch kubeconfig"
			)
			if not response.is_successful():
				printerr("Error while fetching cluster config file")
				return
			DisplayServer.clipboard_set(response.get_data()['kubeconfig'])
		1:
			DisplayServer.clipboard_set(infra.infra_config['web_ui_token'])


func _on_item_pressed(item: ItemCard) -> void:
	OS.shell_open("http://localhost:" + str(int(infra.infra_config['web_ui_port'])))
	#OS.shell_open("http://localhost:30080")
	
