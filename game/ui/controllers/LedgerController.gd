class_name LedgerController
extends Control

var rows: Array[Dictionary] = []
var page: int = 0


func fuzzy_sort_band(value: float) -> int:
	if value < 25.0:
		return 0
	if value < 50.0:
		return 1
	if value < 75.0:
		return 2
	return 3


func set_hidden_rows(source: Array[Dictionary]) -> void:
	rows.clear()
	for i: int in range(source.size()):
		var row: Dictionary = source[i].duplicate()
		row["fuzzy_sort_band"] = fuzzy_sort_band(float(row.get("hidden", 0.0)))
		rows.append(row)
	rows.sort_custom(_by_band)


func _by_band(a: Dictionary, b: Dictionary) -> bool:
	var band_a: int = fuzzy_sort_band(float(a.get("hidden", 0.0)))
	var band_b: int = fuzzy_sort_band(float(b.get("hidden", 0.0)))
	if band_a == band_b:
		return String(a.get("id", "")) < String(b.get("id", ""))
	return band_a < band_b


func display_hidden(row: Dictionary) -> String:
	var band: int = fuzzy_sort_band(float(row.get("hidden", 0.0)))
	var labels: PackedStringArray = PackedStringArray(["低", "中", "高", "极高"])
	return labels[mini(band, 3)]
