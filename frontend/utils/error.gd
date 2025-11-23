class_name Error
extends Script


static func handle_http_error(title: String, result: int, response_code: int):
	OS.alert("Error " + str(response_code), title)
