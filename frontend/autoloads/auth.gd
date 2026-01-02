extends Node


var HTTP_HEADER:
	get():
		return ["Authorization: Bearer " + Config.auth_token]

signal logged_in()
signal logged_out()

var user: User:
	set(val):
		if val:
			logged_in.emit()
			print("User " + val.username + " successfully logged in")
		else:
			logged_out.emit()
			print("User " + user.username + " successfully logged out")
		user = val


func logout():
	Config.auth_token = "null"
	user = null
