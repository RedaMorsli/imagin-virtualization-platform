extends OptionButton


func _ready() -> void:
	var lang = Config.language
	for index in item_count:
		if get_item_text(index).to_lower() == lang:
			select(index)
			break


func _on_lang_selected(index: int) -> void:
	var lang = get_item_text(index).to_lower()
	Config.language = lang
