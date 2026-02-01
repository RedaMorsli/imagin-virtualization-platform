extends DialogScene


func _ready() -> void:
	Events.infra_created.connect(queue_free)
