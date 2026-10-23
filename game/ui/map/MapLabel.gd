class_name MapLabel
extends Node2D

## Centred map text (country / sea / lake / region names) with a paper outline. The canvas
## counter-scales label nodes so the text keeps its screen size at any zoom.

var text: String = ""
var sub_text: String = ""
var font: Font = null
var font_size: int = 13
var sub_font_size: int = 12
var color: Color = Color(0.1176, 0.1098, 0.102, 1)
var outline_color: Color = Color(0.956863, 0.937255, 0.901961, 0.85)
var outline_size: int = 3


func setup(label_text: String, at: Vector2, label_font: Font, size_px: int, label_color: Color, label_sub: String = "") -> void:
	text = label_text
	sub_text = label_sub
	position = at
	font = label_font
	font_size = size_px
	color = label_color
	queue_redraw()


func _draw() -> void:
	if font == null or text == "":
		return
	var main_size: Vector2 = font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size)
	var top: float = -main_size.y * 0.5
	if sub_text != "":
		var sub_size: Vector2 = font.get_string_size(sub_text, HORIZONTAL_ALIGNMENT_LEFT, -1.0, sub_font_size)
		top = -(main_size.y + sub_size.y) * 0.5
		_text_at(sub_text, Vector2(-sub_size.x * 0.5, top + main_size.y + font.get_ascent(sub_font_size)), sub_font_size)
	_text_at(text, Vector2(-main_size.x * 0.5, top + font.get_ascent(font_size)), font_size)


func _text_at(value: String, baseline: Vector2, size_px: int) -> void:
	if outline_size > 0:
		draw_string_outline(font, baseline, value, HORIZONTAL_ALIGNMENT_LEFT, -1.0, size_px, outline_size, outline_color)
	draw_string(font, baseline, value, HORIZONTAL_ALIGNMENT_LEFT, -1.0, size_px, color)
