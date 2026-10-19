class_name LedgerController
extends Control

## Ledger rows for fog-of-war protected attributes (D-088). Each row keeps only the
## coarse band (`fuzzy_sort_band`, `band_centre`) and its rendered text; the raw
## `hidden` float passed in by the caller is dropped and never stored or displayed.

var rows: Array[Dictionary] = []
var page: int = 0
var body: Label


func _ready() -> void:
	_ensure_widgets()


func _ensure_widgets() -> void:
	if body != null:
		return
	body = Label.new()
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_font_size_override("font_size", 14)
	add_child(body)


func fuzzy_sort_band(value: float) -> int:
	return FuzzyBand.band_index(value)


func set_hidden_rows(source: Array[Dictionary]) -> void:
	rows.clear()
	for i: int in range(source.size()):
		var src: Dictionary = source[i]
		var band: int = fuzzy_sort_band(float(src.get("hidden", 0.0)))
		rows.append(_make_row(src, band))
	rows.sort_custom(_by_band)
	_render()


## Builds rows straight from the snapshot's already-banded fuzzy params.
func refresh_from_snapshot(snapshot: SimReadonlySnapshot) -> void:
	rows.clear()
	if snapshot == null:
		_render()
		return
	var ids: Array[String] = SimMath.sorted_keys(snapshot.fuzzy_bands)
	for i: int in range(ids.size()):
		rows.append(_make_row({"id": ids[i], "param_id": ids[i]}, snapshot.read_band(ids[i])))
	rows.sort_custom(_by_band)
	_render()


func _make_row(src: Dictionary, band: int) -> Dictionary:
	var param_id: String = String(src.get("param_id", ""))
	var row: Dictionary = {}
	for key: Variant in src.keys():
		var key_name: String = String(key)
		if key_name == "hidden":
			continue
		var cell: Variant = src[key]
		if typeof(cell) == TYPE_FLOAT:
			continue
		row[key_name] = cell
	row["fuzzy_sort_band"] = band
	row["band_centre"] = FuzzyBand.band_centre(band)
	row["band_label"] = FuzzyBand.band_word(band, param_id)
	row["band_range"] = FuzzyBand.range_text(band)
	row["display"] = FuzzyBand.describe_band(band, param_id)
	return row


func _by_band(a: Dictionary, b: Dictionary) -> bool:
	var centre_a: int = int(a.get("band_centre", 0))
	var centre_b: int = int(b.get("band_centre", 0))
	if centre_a == centre_b:
		return String(a.get("id", "")) < String(b.get("id", ""))
	return centre_a < centre_b


func display_hidden(row: Dictionary) -> String:
	if row.has("display"):
		return String(row["display"])
	return FuzzyBand.describe_band(int(row.get("fuzzy_sort_band", -1)), String(row.get("param_id", "")))


func _render() -> void:
	if body == null:
		return
	var lines: PackedStringArray = PackedStringArray(["国家总账本  情报估算"])
	for i: int in range(rows.size()):
		lines.append("%s  %s" % [String(rows[i].get("id", "")), display_hidden(rows[i])])
	body.text = "\n".join(lines)
