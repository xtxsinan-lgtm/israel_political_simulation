class_name SimContainers
extends RefCounted


static func _due(item: Dictionary) -> int:
	return int(item["due_day"])


static func _seq(item: Dictionary) -> int:
	if item.has("seq"):
		return int(item["seq"])
	if item.has("delayed_seq"):
		return int(item["delayed_seq"])
	return 0


static func _before(a: Dictionary, b: Dictionary) -> bool:
	var ad: int = _due(a)
	var bd: int = _due(b)
	if ad != bd:
		return ad < bd
	return _seq(a) < _seq(b)


static func _sift_up(heap: Array[Dictionary], index: int) -> void:
	var i: int = index
	while i > 0:
		var parent: int = SimMath.idiv_floor(i - 1, 2)
		if not _before(heap[i], heap[parent]):
			break
		var tmp: Dictionary = heap[parent]
		heap[parent] = heap[i]
		heap[i] = tmp
		i = parent


static func _sift_down(heap: Array[Dictionary], index: int) -> void:
	var i: int = index
	var n: int = heap.size()
	while true:
		var left: int = i * 2 + 1
		var right: int = left + 1
		var best: int = i
		if left < n and _before(heap[left], heap[best]):
			best = left
		if right < n and _before(heap[right], heap[best]):
			best = right
		if best == i:
			break
		var tmp: Dictionary = heap[best]
		heap[best] = heap[i]
		heap[i] = tmp
		i = best


static func heap_push(heap: Array[Dictionary], item: Dictionary) -> void:
	heap.append(item)
	_sift_up(heap, heap.size() - 1)


static func heap_pop(heap: Array[Dictionary]) -> Dictionary:
	if heap.is_empty():
		return {}
	var top: Dictionary = heap[0]
	var last: Dictionary = heap[heap.size() - 1]
	heap.remove_at(heap.size() - 1)
	if not heap.is_empty():
		heap[0] = last
		_sift_down(heap, 0)
	return top


static func heap_pop_all_due(heap: Array[Dictionary], current_day: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	while not heap.is_empty() and int(heap[0]["due_day"]) <= current_day:
		out.append(heap_pop(heap))
	return out


static func push_ring_buffer(ring: Array[Dictionary], item: Dictionary, max_cap: int = 12) -> void:
	while ring.size() >= max_cap and max_cap > 0:
		ring.remove_at(0)
	ring.append(item)
