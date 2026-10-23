class_name MapSitePin
extends Node2D

## Site marker: the stem tip sits on the real site position (map_geo.json `sites`). The canvas
## counter-scales the pin so it keeps its screen size while the map zooms.

const PAPER: Color = Color(0.956863, 0.937255, 0.901961, 1.0)

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


func status_color() -> Color:
	match status:
		"planned", "building":
			return Color(0.784, 0.541, 0.118, 1)
		"crisis", "attacked":
			return Color(0.722, 0.161, 0.184, 1)
		"demolished", "removed":
			return Color(0.45, 0.42, 0.38, 1)
		_:
			return Color(0.62, 0.46, 0.16, 1)


func _draw() -> void:
	var head: Vector2 = Vector2(0.0, -9.0)
	draw_line(head, Vector2.ZERO, Color(0.2, 0.16, 0.1), 1.5)
	draw_circle(head, 5.5, PAPER)
	draw_circle(head, 4.5, status_color())
	draw_circle(Vector2.ZERO, 1.2, Color(0.2, 0.16, 0.1))
