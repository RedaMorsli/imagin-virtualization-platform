extends Node


var _http: HTTPRequest = HTTPRequest.new()


func _ready() -> void:
	add_child(_http)


func send_request(
	url: String, 
	headers: PackedStringArray, 
	method: HTTPClient.Method, 
	data: Dictionary = {},
	error_msg: String = ""
	) -> HttpResponse:
	print("Sending HTTP request to " + url)
	var json = JSON.stringify(data)
	var error = _http.request(url, headers, method, json)
	if error != OK:
		printerr("Error when sending http request to '" + url + "' (code " + str(error) + ")")
		if error_msg:
			OS.alert(error_msg + " (error code " + str(error) + ")", "ERROR")
		return null
	var response = await _http.request_completed
	var http_response: HttpResponse = HttpResponse.new.callv(response)
	if not http_response.is_successful():
		print("HTTP request to " + url + " failed: " + str(http_response.get_data()))
	return http_response
