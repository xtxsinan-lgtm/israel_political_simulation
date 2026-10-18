extends SceneTree


func _initialize() -> void:
	quit(_run())


func _run() -> int:
	var packed: PackedScene = load("res://ui/scenes/DeskMain.tscn")
	if packed == null:
		return _fail("desk")
	var desk: DeskMainController = packed.instantiate() as DeskMainController
	if desk == null:
		return _fail("controller")
	root.add_child(desk)
	if desk.map_area_ratio() < 0.60:
		return _fail("map area")
	var drawer: DrawerContainerController = DrawerContainerController.new()
	drawer._ready()
	drawer.toggle_drawer(1)
	drawer.toggle_drawer(3)
	if drawer.visible_drawers_count() > 1:
		return _fail("drawers")
	var tips: CausalTooltipManager = CausalTooltipManager.new()
	tips.lock_tooltip("a")
	tips.lock_tooltip("b")
	tips.lock_tooltip("c")
	if tips.lock_tooltip("d") or tips.locked.size() != 3:
		return _fail("tooltip depth")
	var access: Node = root.get_node("AccessibilityManager")
	var tiny: int = SimMath.round_half_up_int(float(access.call("font_px", 12)))
	if tiny < 12:
		return _fail("font %s" % tiny)
	if _theme_has_small_font():
		return _fail("theme font")
	print("UI_CONSTRAINTS_ALL_PASSED")
	return 0


func _theme_has_small_font() -> bool:
	var file: FileAccess = FileAccess.open("res://ui/theme/mahapach_1977_theme.tres", FileAccess.READ)
	if file == null:
		return true
	var text: String = file.get_as_text()
	file.close()
	var lines: PackedStringArray = text.split("\n")
	for i: int in range(lines.size()):
		if not lines[i].contains("font_size"):
			continue
		var parts: PackedStringArray = lines[i].split("=")
		if parts.size() < 2:
			continue
		var size: int = SimMath.round_half_up_int(float(parts[1].strip_edges()))
		if size < 12:
			return true
	return false


func _fail(message: String) -> int:
	push_error(message)
	print("UI_FAIL %s" % message)
	return 1
