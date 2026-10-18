class_name OnboardingDirector
extends Control

const STEP_COUNT: int = 8

var step: int = 0
var skipped: bool = false
var body: Label


func _ready() -> void:
	if body != null:
		return
	body = Label.new()
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(body)
	_show()


func advance() -> void:
	if skipped:
		return
	step = mini(step + 1, STEP_COUNT)
	_show()


func skip_tutorial() -> void:
	skipped = true
	step = STEP_COUNT
	if body == null:
		_ready()
	body.text = "教程已跳过，全部面板已解锁"


func finished() -> bool:
	return step >= STEP_COUNT


func _show() -> void:
	if body == null:
		return
	var lines: PackedStringArray = PackedStringArray([
		"看顶栏：61 席与政治资本",
		"在地图上查看西奈、西岸和 F1–F7",
		"锁定一个因果提示，看通胀从哪来",
		"打开 D2，核对利库德联盟",
		"打开 D3，处理部长提案和 30% 折扣",
		"打开 D4，看因果网络",
		"读第一份电报和三层预览",
		"解除暂停，走到第一个周日",
	])
	if step >= lines.size():
		body.text = "引导完成"
	else:
		body.text = "第 %d 步  %s" % [step + 1, lines[step]]
