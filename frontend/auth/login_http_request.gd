extends HTTPRequest


@onready var username_edit: LineEdit = %UsernameEdit
@onready var password_edit: LineEdit = %PasswordEdit
@onready var login_button: Button = %LoginButton
@onready var loading_spinner: TextureRect = %LoadingSpinner


func login():
	print("Trying to login...")
	print("Sending log in request to " + API.login_url)
	login_button.hide()
	loading_spinner.show()
	
	var credentials = {
		"username": username_edit.text,
		"password": password_edit.text.sha256_text()
	}
	var json = JSON.stringify(credentials)
	request(
		API.login_url,
		API.HEADERS_JSON,
		HTTPClient.METHOD_POST,
		json
	)


func check_active_session():
	print("Cheking active session...")
	var token = Config.auth_token
	if not token or token == "":
		print("No saved token")
		return
	
	print("Sending log in request to " + API.verify_url)
	login_button.hide()
	loading_spinner.show()
	
	request(
		API.verify_url,
		["Authorization: Bearer " + token],
		HTTPClient.METHOD_GET
	)


func _on_request_completed(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray) -> void:
	login_button.show()
	loading_spinner.hide()

	if result != RESULT_SUCCESS or response_code != HTTPClient.RESPONSE_OK:
		Error.handle_http_error("Failed to login", result, response_code)
		return

	print("Login successful")
	login_button.disabled = true
	
	var json = JSON.parse_string(body.get_string_from_utf8())
	if not json:
		return
	
	print("User: " + json['username'] + " (" + json['role'] + ")")
	if json.has("token"):
		print("Received token: " + json['token'])
		Config.auth_token = json['token']
