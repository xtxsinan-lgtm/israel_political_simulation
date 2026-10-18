class_name CodexAutoLinker
extends RefCounted

var terms: Array[Dictionary] = []


func _init() -> void:
	terms = [
		{"id": "mahapach", "title": "大转折"},
		{"id": "bader_ofer", "title": "巴德尔-奥弗法"},
		{"id": "histadrut", "title": "以色列总工会"},
		{"id": "gush_emunim", "title": "古什埃穆尼姆"},
	]
	if GameData.current != null:
		var raw: Dictionary = GameData.current.codex_terms
		var ids: Array[String] = SimMath.sorted_keys(raw)
		for i: int in range(ids.size()):
			var row: Dictionary = {}
			if typeof(raw[ids[i]]) == TYPE_DICTIONARY:
				row = raw[ids[i]]
			var title: String = String(row.get("title", row.get("name_zh", ids[i])))
			if title != "":
				terms.append({"id": ids[i], "title": title})


func inject_codex_links(raw_text: String) -> String:
	var output: String = raw_text
	var used: Dictionary = {}
	for i: int in range(terms.size()):
		var title: String = String(terms[i].get("title", ""))
		var entry_id: String = String(terms[i].get("id", ""))
		if title == "" or used.has(title) or not output.contains(title):
			continue
		used[title] = true
		var link: String = "[url=codex://%s][color=#0038B8][u]%s[/u][/color][/url]" % [entry_id, title]
		output = output.replace(title, link)
	return output
