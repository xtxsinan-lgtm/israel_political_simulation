class_name SimRNG
extends RefCounted

const MASK32: int = 0xFFFFFFFF
const STREAM_NAMES: Array[String] = [
	"ai", "combat", "core", "economy", "elections",
	"events", "politics", "random_events", "world",
]

var streams: Dictionary = {}
var cosmetic_stream: Stream = Stream.new()
var master_seed: int = 19770620


class Stream extends RefCounted:
	const MASK32: int = 0xFFFFFFFF

	var name: String = ""
	var s0: int = 0
	var s1: int = 0
	var s2: int = 0
	var s3: int = 0
	var draws: int = 0

	static func mul32(a: int, b: int) -> int:
		var a32: int = a & MASK32
		var b32: int = b & MASK32
		var lo: int = a32 * (b32 & 0xFFFF)
		var hi: int = ((a32 * (b32 >> 16)) & 0xFFFF) << 16
		return (lo + hi) & MASK32

	static func rotl32(x: int, k: int) -> int:
		var x32: int = x & MASK32
		var left: int = (x32 << k) & MASK32
		var right: int = x32 >> (32 - k)
		return left | right

	static func fnv1a32(text: String) -> int:
		var h: int = 0x811C9DC5
		var bytes: PackedByteArray = text.to_utf8_buffer()
		for i: int in range(bytes.size()):
			h = mul32(h ^ int(bytes[i]), 0x01000193)
		return h

	static func fmix32(h_in: int) -> int:
		var h: int = h_in & MASK32
		h ^= (h >> 16)
		h = mul32(h, 0x85EBCA6B)
		h ^= (h >> 13)
		h = mul32(h, 0xC2B2AE35)
		h ^= (h >> 16)
		return h & MASK32

	func init_stream(seed: int, stream_name: String) -> void:
		name = stream_name
		var x: int = fmix32((seed & MASK32) ^ fnv1a32(stream_name))
		var st: Array[int] = [0, 0, 0, 0]
		for i: int in range(4):
			x = (x + 0x9E3779B9) & MASK32
			var z: int = x
			z = mul32(z ^ (z >> 16), 0x85EBCA6B)
			z = mul32(z ^ (z >> 13), 0xC2B2AE35)
			z = (z ^ (z >> 16)) & MASK32
			st[i] = z
		if st[0] == 0 and st[1] == 0 and st[2] == 0 and st[3] == 0:
			st[0] = 1
		s0 = st[0]
		s1 = st[1]
		s2 = st[2]
		s3 = st[3]
		draws = 0

	func next_u32() -> int:
		var r: int = mul32(rotl32(mul32(s1, 5), 7), 9)
		var t: int = (s1 << 9) & MASK32
		s2 ^= s0
		s3 ^= s1
		s1 ^= s2
		s0 ^= s3
		s2 ^= t
		s3 = rotl32(s3, 11)
		draws += 1
		return r

	func next_float() -> float:
		return float(next_u32() >> 8) / 16777216.0

	func chance(p: float) -> bool:
		var f: float = next_float()
		return f < p

	func range_int(lo: int, hi: int) -> int:
		var span: int = hi - lo + 1
		if span <= 1:
			next_u32()
			return lo
		return lo + (next_u32() % span)

	func uniform(lo: float, hi: float) -> float:
		return lo + (hi - lo) * next_float()

	func weighted_pick(items: Array, weights: PackedFloat64Array) -> Variant:
		var total_w: float = 0.0
		for i: int in range(weights.size()):
			total_w += weights[i]
		var f: float = next_float()
		if total_w <= 0.0 or items.is_empty():
			if items.is_empty():
				return null
			return items[0]
		var threshold: float = f * total_w
		var acc: float = 0.0
		for i: int in range(items.size()):
			acc += weights[i]
			if acc > threshold:
				return items[i]
		return items[items.size() - 1]

	func shuffle(arr: Array) -> void:
		var n: int = arr.size()
		if n <= 1:
			return
		for i: int in range(n - 1, 0, -1):
			var j: int = range_int(0, i)
			var tmp: Variant = arr[i]
			arr[i] = arr[j]
			arr[j] = tmp

	func to_dict() -> Dictionary:
		return {
			"s0": s0,
			"s1": s1,
			"s2": s2,
			"s3": s3,
			"draws": draws,
		}


func init_from_master_seed(seed: int) -> void:
	master_seed = seed & Stream.MASK32
	streams = {}
	for i: int in range(STREAM_NAMES.size()):
		var stream_name: String = STREAM_NAMES[i]
		var created: Stream = Stream.new()
		created.init_stream(master_seed, stream_name)
		streams[stream_name] = created
	cosmetic_stream = Stream.new()
	cosmetic_stream.init_stream(master_seed, SimTypes.COSMETIC_RNG_STREAM)


func get_stream(stream_name: String) -> Stream:
	if stream_name == SimTypes.COSMETIC_RNG_STREAM:
		return cosmetic_stream
	if streams.has(stream_name):
		return streams[stream_name] as Stream
	var created: Stream = Stream.new()
	created.init_stream(master_seed, stream_name)
	streams[stream_name] = created
	return created


func to_dict() -> Dictionary:
	var out_streams: Dictionary = {}
	var keys: Array[String] = SimMath.sorted_keys(streams)
	for i: int in range(keys.size()):
		var key: String = keys[i]
		if key == SimTypes.COSMETIC_RNG_STREAM:
			continue
		var st: Stream = streams[key] as Stream
		out_streams[key] = st.to_dict()
	return {"master_seed": master_seed, "streams": out_streams}


func from_dict(d: Dictionary, seed: int) -> void:
	var use_seed: int = seed
	if d.has("master_seed"):
		use_seed = int(d["master_seed"])
	init_from_master_seed(use_seed)
	var raw_streams: Variant = d.get("streams", {})
	if typeof(raw_streams) != TYPE_DICTIONARY:
		return
	var table: Dictionary = raw_streams
	var keys: Array[String] = SimMath.sorted_keys(table)
	for i: int in range(keys.size()):
		var key: String = keys[i]
		if key == SimTypes.COSMETIC_RNG_STREAM:
			continue
		var entry_v: Variant = table[key]
		if typeof(entry_v) != TYPE_DICTIONARY:
			continue
		var entry: Dictionary = entry_v
		var st: Stream = get_stream(key)
		st.s0 = int(entry.get("s0", st.s0)) & Stream.MASK32
		st.s1 = int(entry.get("s1", st.s1)) & Stream.MASK32
		st.s2 = int(entry.get("s2", st.s2)) & Stream.MASK32
		st.s3 = int(entry.get("s3", st.s3)) & Stream.MASK32
		if st.s0 == 0 and st.s1 == 0 and st.s2 == 0 and st.s3 == 0:
			st.s0 = 1
		if entry.has("draws"):
			st.draws = int(entry["draws"])
		elif entry.has("calls"):
			st.draws = int(entry["calls"])


func export_draws() -> Dictionary:
	var out: Dictionary = {}
	for i: int in range(STREAM_NAMES.size()):
		var stream_name: String = STREAM_NAMES[i]
		var st: Stream = get_stream(stream_name)
		out[stream_name] = st.draws
	return out


static func verify_t01_golden_vectors() -> bool:
	if Stream.fnv1a32("events") != 316203908:
		return false
	var core: Stream = Stream.new()
	core.init_stream(19770620, "core")
	var core_draws: Array[int] = [core.next_u32(), core.next_u32(), core.next_u32()]
	if core_draws[0] != 1043188165 or core_draws[1] != 3233761027 or core_draws[2] != 729440262:
		return false
	var events: Stream = Stream.new()
	events.init_stream(19770620, "events")
	var event_draws: Array[int] = [events.next_u32(), events.next_u32(), events.next_u32()]
	if event_draws[0] != 4038072526 or event_draws[1] != 988157684 or event_draws[2] != 1135148507:
		return false
	return true
