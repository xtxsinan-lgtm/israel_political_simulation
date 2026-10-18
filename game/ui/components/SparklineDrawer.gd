class_name SparklineDrawer
extends Control

var series: PackedFloat64Array = PackedFloat64Array()
var warn_at: float = -1.0
var line_color: Color = Color(0.0, 0.22, 0.72, 1)


func set_series(values: PackedFloat64Array, threshold: float = -1.0) -> void:
	series = values
	warn_at = threshold
	queue_redraw()


func _draw() -> void:
	if series.size() < 2:
		return
	var lo: float = series[0]
	var hi: float = series[0]
	for i: int in range(series.size()):
		lo = minf(lo, series[i])
		hi = maxf(hi, series[i])
	if absf(hi - lo) < 0.001:
		hi = lo + 1.0
	var points: PackedVector2Array = PackedVector2Array()
	var width: float = size.x
	var height: float = size.y
	for i: int in range(series.size()):
		var x: float = width * float(i) / float(series.size() - 1)
		var y: float = height - (series[i] - lo) / (hi - lo) * height
		points.append(Vector2(x, y))
	var fill: PackedVector2Array = points.duplicate()
	fill.append(Vector2(width, height))
	fill.append(Vector2(0, height))
	draw_colored_polygon(fill, Color(line_color.r, line_color.g, line_color.b, 0.18))
	draw_polyline(points, line_color, 1.5, true)
	draw_circle(points[points.size() - 1], 3.0, line_color)
	if warn_at >= lo and warn_at <= hi:
		var y_warn: float = height - (warn_at - lo) / (hi - lo) * height
		draw_dashed_line(Vector2(0, y_warn), Vector2(width, y_warn), Color(0.722, 0.161, 0.184), 1.0)
