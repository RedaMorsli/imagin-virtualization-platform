extends PanelContainer

var infra: Infra

@onready var name_label: Label = %NameLabel
@onready var available_nodes_label: Label = %AvailableNodesLabel
@onready var total_nodes_label: Label = %TotalNodesLabel
@onready var status_label: Label = %StatusLabel


func _ready() -> void:
	if not infra:
		return
	name_label.text = infra.infra_config['name']
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
