extends Node


var _http: HTTPRequest = HTTPRequest.new()


func _ready() -> void:
	add_child(_http)


func send_request(
	url: String, 
	headers: PackedStringArray, 
	method: HTTPClient.Method, 
	data: String = "",
	error_msg: String = ""
	) -> HttpResponse:
	var error = _http.request(url, headers, method, data)
	if error != OK:
		printerr("Error when sending http request to '" + url + "' (code " + str(error) + ")")
		if error_msg:
			OS.alert(error_msg + " (error code " + str(error) + ")", "ERROR")
		return null
	var response = await _http.request_completed
	var http_response = HttpResponse.new.callv(response)
	return http_response
