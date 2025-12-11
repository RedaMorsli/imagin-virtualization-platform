extends TextureRect


const ROTATION_CYCLE_TIME = 1


func _ready() -> void:
	pivot_offset = size / 2
	var tween = create_tween()
	tween.set_loops()
	tween.tween_property(self, "rotation_degrees", 360, ROTATION_CYCLE_TIME).from(0)
