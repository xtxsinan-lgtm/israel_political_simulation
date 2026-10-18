class_name MapSitePin
extends Node2D

var site_id: String = ""
var region_id: String = ""
var status: String = "active"
var title_zh: String = ""


func setup(site: Dictionary, at: Vector2) -> void:
	site_id = String(site.get("site_id", ""))
	region_id = String(site.get("region_id", ""))
	status = String(site.get("status", "active"))
	title_zh = String(site.get("name_zh", site_id))
	position = at
	queue_redraw()


func _draw() -> void:
	var color: Color = Color(0.72, 0.55, 0.22, 1)
	match status:
		"planned", "building":
			color = Color(0.784, 0.541, 0.118, 1)
		"crisis", "attacked":
			color = Color(0.722, 0.161, 0.184, 1)
		"demolished", "removed":
			color = Color(0.45, 0.42, 0.38, 1)
		_:
			color = Color(0.62, 0.46, 0.16, 1)
	draw_circle(Vector2.ZERO, 5.0, color)
	draw_line(Vector2(0, 0), Vector2(0, 10), Color(0.2, 0.16, 0.1), 1.5)
