extends VBoxContainer


const NewExperimentDialog = preload("uid://cg6sftdi0e37l")

@onready var _new_btn: Button
@onready var _spinner: Node
@onready var _error_lbl: Label
@onready var _empty_lbl: Label
@onready var _cards_list: VBoxContainer


func _ready() -> void:
	add_theme_constant_override("separation", 16)

	# ── Header row ────────────────────────────────────────────────────────────
	var header := HBoxContainer.new()
	var title := Label.new()
	title.text = "EXPERIMENTS"
	title.theme_type_variation = "HeaderLarge"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_new_btn = Button.new()
	_new_btn.text = "NEW_EXPERIMENT"
	_new_btn.theme_type_variation = "PrimaryButton"
	_new_btn.pressed.connect(_on_new_pressed)
	header.add_child(title)
	header.add_child(_new_btn)
	add_child(header)

	# ── Loading spinner ───────────────────────────────────────────────────────
	var spinner_scene = load("res://components/loading/loading_spinner.tscn")
	_spinner = spinner_scene.instantiate()
	_spinner.visible = false
	add_child(_spinner)

	# ── Error / empty labels ──────────────────────────────────────────────────
	_error_lbl = Label.new()
	_error_lbl.theme_type_variation = "ErrorLabel"
	_error_lbl.visible = false
	_error_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD
	add_child(_error_lbl)

	_empty_lbl = Label.new()
	_empty_lbl.text = "NO_EXPERIMENTS_MSG"
	_empty_lbl.theme_type_variation = "SecondaryText"
	_empty_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_empty_lbl.visible = false
	add_child(_empty_lbl)

	# ── Cards scroll area ─────────────────────────────────────────────────────
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(scroll)

	_cards_list = VBoxContainer.new()
	_cards_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_cards_list.add_theme_constant_override("separation", 8)
	scroll.add_child(_cards_list)

	_fetch_experiments()


func _fetch_experiments() -> void:
	_spinner.show()
	_error_lbl.visible = false
	_empty_lbl.visible = false
	for c in _cards_list.get_children():
		c.queue_free()

	var response = await Http.send_request(
		API.fetch_experiments_url + "?project_id=" + str(Context.project.project_id),
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_GET,
	)
	_spinner.hide()

	if not response or not response.is_successful():
		_error_lbl.text = response.get_error() if response else "FETCH_FAILED"
		_error_lbl.visible = true
		return

	var experiments: Array = response.get_data().get("experiments", [])
	if experiments.is_empty():
		_empty_lbl.visible = true
		return

	for exp_data in experiments:
		var card := ExperimentCard.new()
		card.setup(exp_data)
		_cards_list.add_child(card)


func _on_new_pressed() -> void:
	var dialog = Dialog.popup(NewExperimentDialog.instantiate())
	dialog.completed.connect(_fetch_experiments)
