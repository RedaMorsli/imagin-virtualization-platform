extends Page


@onready var upload_button: Button = %UploadButton
@onready var loading_spinner: TextureRect = %LoadingSpinner
@onready var error_label: Label = %ErrorLabel
@onready var empty_label: Label = %EmptyLabel
@onready var file_scroll: ScrollContainer = %FileScroll
@onready var file_list: VBoxContainer = %FileList
@onready var file_dialog: FileDialog = %FileDialog

# Held as a member to prevent the JS object from being garbage-collected.
var _js_callback: JavaScriptObject


func _ready() -> void:
	_fetch_files()


func _fetch_files() -> void:
	loading_spinner.show()
	error_label.hide()
	empty_label.hide()
	file_scroll.hide()

	var response = await Http.send_request(
		API.list_files_url + "?project_id=" + str(Context.project.project_id),
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_GET
	)
	loading_spinner.hide()

	if not response or not response.is_successful():
		error_label.text = response.get_error() if response else "FETCH_FAILED"
		error_label.show()
		return

	for child in file_list.get_children():
		child.queue_free()

	var files: Array = response.get_data().get("files", [])

	if files.is_empty():
		empty_label.show()
		return

	file_scroll.show()
	for file_info in files:
		_add_file_row(file_info["name"], file_info["size"])


func _add_file_row(file_name: String, file_size: int) -> void:
	var row = HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)

	var name_label = Label.new()
	name_label.text = file_name
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name_label.theme_type_variation = "SecondaryText"

	var size_label = Label.new()
	size_label.text = _format_size(file_size)
	size_label.custom_minimum_size.x = 80
	size_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	size_label.theme_type_variation = "SecondaryText"

	var delete_btn = Button.new()
	delete_btn.text = "DELETE"
	delete_btn.pressed.connect(_on_delete_pressed.bind(file_name, row))

	row.add_child(name_label)
	row.add_child(size_label)
	row.add_child(delete_btn)
	file_list.add_child(row)


func _format_size(bytes: int) -> String:
	if bytes < 1024:
		return str(bytes) + " B"
	elif bytes < 1048576:
		return "%.1f KB" % (bytes / 1024.0)
	return "%.1f MB" % (bytes / 1048576.0)


func _on_upload_pressed() -> void:
	if OS.has_feature("web"):
		_open_web_file_picker()
	else:
		file_dialog.popup_centered_ratio(0.75)


# ---- Web file picker ----

func _open_web_file_picker() -> void:
	# Keep a strong reference so the JS object is not collected between clicks.
	_js_callback = JavaScriptBridge.create_callback(_on_web_file_received)
	JavaScriptBridge.get_interface("window")["_godotStorageUpload"] = _js_callback

	JavaScriptBridge.eval("""
		(function() {
			var input = document.createElement('input');
			input.type = 'file';
			input.style.display = 'none';
			document.body.appendChild(input);
			input.addEventListener('change', function() {
				var file = input.files[0];
				if (!file) { document.body.removeChild(input); return; }
				var reader = new FileReader();
				reader.onload = function(ev) {
					var bytes = new Uint8Array(ev.target.result);
					var binary = '';
					for (var i = 0; i < bytes.byteLength; i++) {
						binary += String.fromCharCode(bytes[i]);
					}
					window._godotStorageUpload(file.name, btoa(binary));
					document.body.removeChild(input);
				};
				reader.readAsArrayBuffer(file);
			});
			input.click();
		})();
	""")


func _on_web_file_received(args: Array) -> void:
	var file_name: String = str(args[0])
	var b64_data: String = str(args[1])
	var file_data: PackedByteArray = Marshalls.base64_to_raw(b64_data)
	_upload_data(file_name, file_data)


# ---- Desktop file picker ----

func _on_file_selected(path: String) -> void:
	var file = FileAccess.open(path, FileAccess.READ)
	if not file:
		error_label.text = "OPEN_FILE_FAILED"
		error_label.show()
		return
	var file_data = file.get_buffer(file.get_length())
	file.close()
	_upload_data(path.get_file(), file_data)


# ---- Shared upload logic ----

func _upload_data(file_name: String, file_data: PackedByteArray) -> void:
	error_label.hide()
	upload_button.disabled = true
	loading_spinner.show()

	var boundary = "Boundary" + str(Time.get_ticks_msec())

	var body = PackedByteArray()
	var part_project_id = (
		"--" + boundary + "\r\n"
		+ "Content-Disposition: form-data; name=\"project_id\"\r\n\r\n"
		+ str(Context.project.project_id) + "\r\n"
	)
	var part_file_header = (
		"--" + boundary + "\r\n"
		+ "Content-Disposition: form-data; name=\"file\"; filename=\"" + file_name + "\"\r\n"
		+ "Content-Type: application/octet-stream\r\n\r\n"
	)
	body.append_array(part_project_id.to_utf8_buffer())
	body.append_array(part_file_header.to_utf8_buffer())
	body.append_array(file_data)
	body.append_array(("\r\n--" + boundary + "--\r\n").to_utf8_buffer())

	var headers = PackedStringArray([
		"Authorization: Bearer " + Config.auth_token,
		"Content-Type: multipart/form-data; boundary=" + boundary,
	])

	var request = HTTPRequest.new()
	add_child(request)
	var err = request.request_raw(API.upload_file_url, headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		error_label.text = "UPLOAD_FAILED"
		error_label.show()
		request.queue_free()
		upload_button.disabled = false
		loading_spinner.hide()
		return

	var result = await request.request_completed
	request.queue_free()
	upload_button.disabled = false
	loading_spinner.hide()

	var response = HttpResponse.new.callv(result)
	if not response.is_successful():
		var data = response.get_data()
		error_label.text = data.get("detail", "UPLOAD_FAILED") if data else "UPLOAD_FAILED"
		error_label.show()
		return

	_fetch_files()


func _on_delete_pressed(file_name: String, row: Node) -> void:
	var response = await Http.send_request(
		API.delete_file_url,
		Auth.HTTP_HEADER,
		HTTPClient.METHOD_DELETE,
		{"project_id": Context.project.project_id, "object_name": file_name}
	)
	if not response or not response.is_successful():
		error_label.text = response.get_error() if response else "DELETE_FAILED"
		error_label.show()
		return

	var remaining = file_list.get_child_count() - 1
	row.queue_free()
	if remaining == 0:
		file_scroll.hide()
		empty_label.show()
