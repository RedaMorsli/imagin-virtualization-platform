extends Control


const MAIN_SCENE = preload("uid://v8pl058l81vh")

@onready var username_edit: LineEdit = %UsernameEdit
@onready var password_edit: LineEdit = %PasswordEdit
@onready var login_button: Button = %LoginButton
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var error_label: Label = %ErrorLabel


func _ready() -> void:
	Auth.logged_in.connect(
		func ():
			get_tree().change_scene_to_packed(MAIN_SCENE)
	)
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
	var response: HttpResponse = await Http.send_request(
		API.login_url,
		API.HEADERS_JSON,
		HTTPClient.METHOD_POST,
		json,
		"LOGIN_FAILED"
	)
	
	_on_login_response(response)


func check_active_session():
	print("Cheking active session...")
	var token = Config.auth_token
	if not token or token == "":
		print("No saved token")
		return
	
	print("Sending login request to " + API.verify_url)
	login_button.hide()
	loading_spinner.show()
	
	var response: HttpResponse = await Http.send_request(
		API.verify_url,
		["Authorization: Bearer " + token],
		HTTPClient.METHOD_GET
	)
	
	_on_login_response(response, false)


func _on_login_response(response: HttpResponse, show_error: bool = true):
	if not response.is_successful():
		login_button.show()
		loading_spinner.hide()
		if not response:
			return
		error_label.text = response.get_error()
		if show_error:
			error_label.show()
		return
	
	var auth_data = response.get_data()
	Auth.user = User.new(
		auth_data['user_id'],
		auth_data['username'],
		auth_data['role']
	)
	if auth_data.has("token"):
		print("Received token: " + auth_data['token'])
		Config.auth_token = auth_data['token']
