extends Node


const _SAVE_PATH = "user://config.cfg"
const _SAVE_PASS = "?1x.y30e%2i8B#E-ptuK4ZNi*h)h+t3B"
const _DEFAULT_SECTION = "config"

var _config: ConfigFile = ConfigFile.new()
var _saved_params: Array = ["auth_token", "language"]


var auth_token: String:
	set(value):
		if not value or not value is String:
			return
		auth_token = value
		_save()

var language: String:
	set(value):
		if not value or not value is String:
			language = OS.get_locale_language()
		else:
			language = value
		TranslationServer.set_locale(language)
		_save()

func _ready() -> void:
	_load()


func _save():
	for param in _saved_params:
		_config.set_value(_DEFAULT_SECTION, param, get(param))
	_config.save(_SAVE_PATH)


func _load():
	var config = ConfigFile.new() 
	var err = config.load(_SAVE_PATH)
	if err != OK:
		print("Error loading config")
		return
	for param in _saved_params:
		var value = config.get_value(_DEFAULT_SECTION, param)
		set(param, value)
