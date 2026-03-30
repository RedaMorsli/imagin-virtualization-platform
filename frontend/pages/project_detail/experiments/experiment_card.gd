class_name ExperimentCard
extends PanelContainer

var experiment: Dictionary

var _runs_list: VBoxContainer
var _runs_empty: Label
var _runs_spinner: Node
var _launch_btn: Button
var _error_label: Label
var _fetched := false


func setup(exp_data: Dictionary) -> void:
	experiment = exp_data


func _ready() -> void:
	theme_type_variation = &"Card"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left",   12)
	margin.add_theme_constant_override("margin_top",    12)
	margin.add_theme_constant_override("margin_right",  12)
	margin.add_theme_constant_override("margin_bottom", 12)
	add_child(margin)

	var foldable := FoldableContainer.new()
	foldable.title    = experiment.get("experiment_name", "Experiment")
	foldable.expanded = false
	foldable.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	foldable.folding_state_changed.connect(_on_fold_changed)
	margin.add_child(foldable)

	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 8)
	foldable.add_child(content)

	# ── Config summary ────────────────────────────────────────────────────────
	var cfg: Dictionary = experiment.get("experiment_config", {})
	var type_lbl := Label.new()
	type_lbl.text = "FL_FLOWER"
	type_lbl.add_theme_type_variation("SecondaryText")
	content.add_child(type_lbl)

	_add_row(content, "FL_CLIENTS", str(cfg.get("num_clients", "—")))
	_add_row(content, "FL_ROUNDS",  str(cfg.get("num_rounds",  "—")))
	_add_row(content, "FL_CPU_LIMIT",    str(cfg.get("cpu_limit",       "—")))
	_add_row(content, "FL_MEMORY_LIMIT", str(cfg.get("memory_limit_mb", "—")) + " MB")

	# ── Action row ────────────────────────────────────────────────────────────
	var action_row := HBoxContainer.new()
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	_error_label = Label.new()
	_error_label.add_theme_type_variation("ErrorLabel")
	_error_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_error_label.visible = false

	var delete_btn := Button.new()
	delete_btn.text = "DELETE"
	delete_btn.pressed.connect(_on_delete_pressed)

	_launch_btn = Button.new()
	_launch_btn.text = "FL_LAUNCH_RUN"
	_launch_btn.add_theme_type_variation("PrimaryButton")
	_launch_btn.pressed.connect(_on_launch_pressed)

	action_row.add_child(_error_label)
	action_row.add_child(spacer)
	action_row.add_child(delete_btn)
	action_row.add_child(_launch_btn)
	content.add_child(action_row)

	content.add_child(HSeparator.new())

	# ── Runs section ─────────────────────────────────────────────────────────
	var spinner_scene = load("res://components/loading/loading_spinner.tscn")
	_runs_spinner = spinner_scene.instantiate()
	_runs_spinner.visible = false
	content.add_child(_runs_spinner)

	_runs_empty = Label.new()
	_runs_empty.text = "FL_NO_RUNS"
	_runs_empty.add_theme_type_variation("SecondaryText")
	_runs_empty.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_runs_empty.visible = false
	content.add_child(_runs_empty)

	_runs_list = VBoxContainer.new()
	_runs_list.add_theme_constant_override("separation", 4)
	content.add_child(_runs_list)


func _add_row(parent: VBoxContainer, key: String, value: String) -> void:
	var row := HBoxContainer.new()
	var lbl := Label.new()
	lbl.text = key
	lbl.add_theme_type_variation("SecondaryText")
	lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var val := Label.new()
	val.text = value
	row.add_child(lbl)
	row.add_child(val)
	parent.add_child(row)


# ── Fold toggle ───────────────────────────────────────────────────────────────

func _on_fold_changed(is_folded: bool) -> void:
	if not is_folded and not _fetched:
		_fetch_runs()


# ── Runs fetch ────────────────────────────────────────────────────────────────

func _fetch_runs() -> void:
	_fetched = true
	_runs_spinner.show()
	_runs_empty.hide()
	for c in _runs_list.get_children():
		c.queue_free()

	var response = await Http.send_request(
		API.fetch_runs_url + "?experiment_id=" + str(experiment["experiment_id"]),
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_GET,
	)
	_runs_spinner.hide()

	if not response or not response.is_successful():
		_runs_empty.text = response.get_error() if response else "FETCH_FAILED"
		_runs_empty.show()
		return

	var runs: Array = response.get_data().get("runs", [])
	if runs.is_empty():
		_runs_empty.text = "FL_NO_RUNS"
		_runs_empty.show()
		return

	for run in runs:
		_add_run_row(run)


func _add_run_row(run: Dictionary) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)

	var status_lbl := Label.new()
	var raw_status: String = run.get("status", "unknown")
	status_lbl.text = "FL_RUN_STATUS_" + raw_status.to_upper()
	match raw_status:
		"completed":  status_lbl.add_theme_type_variation("SuccessLabel")
		"failed":     status_lbl.add_theme_type_variation("ErrorLabel")
		_:            status_lbl.add_theme_type_variation("SecondaryText")
	status_lbl.custom_minimum_size.x = 120

	var date_lbl := Label.new()
	var started: String = run.get("started_at", "")
	date_lbl.text = started.left(16) if started else "—"
	date_lbl.add_theme_type_variation("SecondaryText")
	date_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var metrics_lbl := Label.new()
	var fm: Dictionary = run.get("final_metrics", {})
	if fm.has("accuracy") and fm.has("loss"):
		metrics_lbl.text = "acc %.3f  loss %.3f" % [float(fm["accuracy"]), float(fm["loss"])]
	elif fm.has("accuracy"):
		metrics_lbl.text = "acc %.3f" % float(fm["accuracy"])
	elif fm.has("loss"):
		metrics_lbl.text = "loss %.3f" % float(fm["loss"])
	metrics_lbl.add_theme_type_variation("SecondaryText")

	row.add_child(status_lbl)
	row.add_child(date_lbl)
	row.add_child(metrics_lbl)
	_runs_list.add_child(row)


# ── Actions ───────────────────────────────────────────────────────────────────

func _on_launch_pressed() -> void:
	_launch_btn.disabled = true
	_error_label.visible = false

	var response = await Http.send_request(
		API.launch_run_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_POST,
		{"experiment_id": experiment["experiment_id"]}
	)

	_launch_btn.disabled = false

	if not response or not response.is_successful():
		_error_label.text = response.get_error() if response else "LAUNCH_FAILED"
		_error_label.visible = true
		return

	# Re-fetch runs to show the new provisioning entry
	_fetched = false
	_fetch_runs()


func _on_delete_pressed() -> void:
	var response = await Http.send_request(
		API.delete_experiment_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_POST,
		{
			"project_id":    Context.project.project_id,
			"experiment_id": experiment["experiment_id"],
		}
	)
	if not response or not response.is_successful():
		_error_label.text = response.get_error() if response else "DELETE_FAILED"
		_error_label.visible = true
		return
	queue_free()
