class_name HttpResponse
extends Resource


@export var result: int

@export var response_code: int

@export var headers: PackedStringArray

@export var body: PackedByteArray


func _init(p_result: int, p_response, p_headers: PackedStringArray, p_body: PackedByteArray) -> void:
	result = p_result
	response_code = p_response
	headers = p_headers
	body = p_body


func get_data():
	return JSON.parse_string(body.get_string_from_utf8())


func get_error():
	return get_data()['detail']


func is_successful() -> bool:
	return result == HTTPRequest.RESULT_SUCCESS and response_code == HTTPClient.RESPONSE_OK
