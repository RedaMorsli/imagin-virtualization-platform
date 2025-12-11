class_name User
extends Resource

enum Role {ADMIN, USER}

const RoleMap = {
	'admin': Role.ADMIN,
	'user': Role.USER
}

@export var id: int
@export var username: String
@export var role: Role


func _init(p_id: int, p_username: String, p_role: String) -> void:
	id = p_id
	username = p_username
	role = RoleMap[p_role]
