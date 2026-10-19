class_name D6PalestiniansController
extends Control

var factions: PackedStringArray = PackedStringArray([
	"fatah", "pflp", "jordan_notables", "local_mayors", "village_leagues", "mujama", "hamas", "pij", "pa_security",
])

var pal_legitimacy: Dictionary = {}
var intifada_phase: String = "calm"
var summary: Label


func _ready() -> void:
	if summary != null:
		return
	summary = Label.new()
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(summary)


func refresh(state: SimState) -> void:
	if summary == null:
		_ready()
	var total: float = 0.0
	for i: int in range(factions.size()):
		var share: float = state.params.get_val("faction_legitimacy", factions[i], state)
		pal_legitimacy[factions[i]] = share
		total += share
	if total <= 0.0:
		var even: float = 100.0 / float(factions.size())
		total = 0.0
		for i: int in range(factions.size()):
			pal_legitimacy[factions[i]] = even
			total += even
	elif absf(total - 100.0) > 0.001:
		var scale: float = 100.0 / total
		total = 0.0
		for i: int in range(factions.size()):
			var scaled: float = float(pal_legitimacy[factions[i]]) * scale
			pal_legitimacy[factions[i]] = scaled
			total += scaled
	# uprising_risk and faction_legitimacy are `visible: fuzzy` (D-088): only bands reach the UI.
	var uprising_band: int = FuzzyBand.band_index(state.params.get_val("uprising_risk", "", state))
	if uprising_band >= 3:
		intifada_phase = "intifada"
	elif uprising_band >= 2:
		intifada_phase = "unrest"
	else:
		intifada_phase = "calm"
	summary.text = "阶段 %s  起义风险 %s\nmujama %s  hamas %s" % [
		intifada_phase,
		FuzzyBand.describe_band(uprising_band, "uprising_risk"),
		FuzzyBand.describe(float(pal_legitimacy["mujama"]), "faction_legitimacy"),
		FuzzyBand.describe(float(pal_legitimacy["hamas"]), "faction_legitimacy"),
	]


func legitimacy_sum() -> float:
	var total: float = 0.0
	for i: int in range(factions.size()):
		total += float(pal_legitimacy.get(factions[i], 0.0))
	return total
