extends DialogScene


@onready var name_edit: LineEdit   = %EmptyInfraName
@onready var clients_spin: SpinBox = %FlowerClients
@onready var cpu_spin: SpinBox     = %FlowerCpuLimit
@onready var memory_spin: SpinBox  = %FlowerMemoryLimit
@onready var loading_spinner       = %FlowerLoadingSpinner
@onready var create_button: Button = %FlowerCreateButton
@onready var cancel_button: Button = $CenterContainer/Panel/HBoxContainer/Container/Flower/FlowerButtons/CancelButton
@onready var metric_log_option_button: OptionButton = %MetricOptionButton
@onready var wandb_key_container: HBoxContainer = %WandbKeyContainer
@onready var wandb_entity_container: HBoxContainer = %WandbEntityContainer
@onready var wandb_key_edit: LineEdit = %WandbKeyEdit
@onready var wandb_entity_edit: LineEdit = %WandbEntityEdit


func _ready() -> void:
	cancel_button.pressed.connect(queue_free)


func _on_create_button_pressed() -> void:
	var name = name_edit.text.strip_edges()
	if name.is_empty():
		return

	create_button.disabled = true
	loading_spinner.show()

	var data = {
		"project_id": Context.project.project_id,
		"experiment_type": "fl_flower",
		"experiment_config": {
			"name":            name,
			"num_clients":     int(clients_spin.value),
			"num_rounds":      3,
			"cpu_limit":       str(int(cpu_spin.value)) + "m",
			"memory_limit_mb": int(memory_spin.value),
			"metric_logging":  metric_log_option_button.get_item_text(metric_log_option_button.selected).to_lower(),
			"wandb_api_key":   wandb_key_edit.text,
			"wandb_entity":    wandb_entity_edit.text,
			 "client_selection": {
				"algorithm": %CSAOptionButton.get_item_text(%CSAOptionButton.selected).to_lower(),
				"params": { "num_selected": %NumberClientPerRound.value }
			}
		}
	}

	var response = await Http.send_request(
		API.create_experiment_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_POST,
		data,
		"Failed to create experiment"
	)

	loading_spinner.hide()
	create_button.disabled = false

	if response and response.is_successful():
		completed.emit()
		queue_free()


func _on_metric_option_button_item_selected(index: int) -> void:
	var show_wandb := index == 1
	wandb_key_container.visible = show_wandb
	wandb_entity_container.visible = show_wandb


func _on_csa_option_button_item_selected(index: int) -> void:
	%RandomParams.visible = index == 1
