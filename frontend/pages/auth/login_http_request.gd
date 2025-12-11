extends HTTPRequest


@onready var username_edit: LineEdit = %UsernameEdit
@onready var password_edit: LineEdit = %PasswordEdit
@onready var login_button: Button = %LoginButton
@onready var loading_spinner: TextureRect = %LoadingSpinner

var _show_error: bool = true


func _ready() -> void:
	check_active_session()


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
	_show_error = true
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
	
	print("Sending login request to " + API.verify_url)
	login_button.hide()
	loading_spinner.show()
	
	_show_error = false
	request(
		API.verify_url,
		["Authorization: Bearer " + token],
		HTTPClient.METHOD_GET
	)


func _on_request_completed(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray) -> void:
	login_button.show()
	loading_spinner.hide()

	if result != RESULT_SUCCESS or response_code != HTTPClient.RESPONSE_OK:
		if _show_error:
			Error.handle_http_error("Failed to login", result, response_code)
		return

	login_button.disabled = true
	
	var auth_data = JSON.parse_string(body.get_string_from_utf8())
	if not auth_data:
		print("Failed to get login data")
	
	Auth.user = User.new(
		auth_data['user_id'],
		auth_data['username'],
		auth_data['role']
	)
	
	if auth_data.has("token"):
		print("Received token: " + auth_data['token'])
		Config.auth_token = auth_data['token']
