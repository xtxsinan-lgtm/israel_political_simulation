class_name CanonicalSerializer
extends RefCounted

const EXCLUDED_TOP_KEYS: Dictionary = {
	"run": true,
	"input_log": true,
	"stats": true,
	"errors": true,
}

const EXCLUDED_META_KEYS: Dictionary = {
	"game_version": true,
	"ruleset_hash": true,
	"modified": true,
	"created_real_time": true,
}


static func compute_state_hash_sha256(state: SimState) -> String:
	var canonical_json: String = to_canonical_json_string(state.to_raw_state_dict())
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(canonical_json.to_utf8_buffer())
	var digest: PackedByteArray = ctx.finish()
	return digest.hex_encode().to_lower()


static func to_canonical_json_string(root_dict: Dictionary) -> String:
	var chunks: PackedStringArray = PackedStringArray()
	_serialize_value(root_dict, "", chunks)
	return "".join(chunks)


static func _serialize_array(arr: Array, parent_path: String, out: PackedStringArray) -> void:
	out.append("[")
	for i: int in range(arr.size()):
		if i > 0:
			out.append(",")
		_serialize_value(arr[i], parent_path, out)
	out.append("]")


static func _serialize_value(val: Variant, parent_path: String, out: PackedStringArray) -> void:
	match typeof(val):
		TYPE_NIL:
			out.append("null")
		TYPE_BOOL:
			out.append("true" if bool(val) else "false")
		TYPE_INT, TYPE_FLOAT:
			var canon_i: int = SimMath.to_canonical_int(val)
			out.append(str(canon_i))
		TYPE_STRING:
			out.append(_escape_json_string(String(val)))
		TYPE_ARRAY:
			var arr: Array = val
			_serialize_array(arr, parent_path, out)
		TYPE_PACKED_FLOAT64_ARRAY:
			var floats: PackedFloat64Array = val
			_serialize_array(Array(floats), parent_path, out)
		TYPE_PACKED_INT64_ARRAY:
			var ints: PackedInt64Array = val
			_serialize_array(Array(ints), parent_path, out)
		TYPE_PACKED_STRING_ARRAY:
			var strs: PackedStringArray = val
			_serialize_array(Array(strs), parent_path, out)
		TYPE_PACKED_BYTE_ARRAY:
			var bytes: PackedByteArray = val
			_serialize_array(Array(bytes), parent_path, out)
		TYPE_DICTIONARY:
			var d: Dictionary = val
			var sorted_k: Array[String] = SimMath.sorted_keys(d)
			out.append("{")
			var first: bool = true
			for k: String in sorted_k:
				if parent_path == "" and EXCLUDED_TOP_KEYS.has(k):
					continue
				if parent_path == "meta" and EXCLUDED_META_KEYS.has(k):
					continue
				if parent_path == "rng" and k == "cosmetic":
					continue
				if not d.has(k):
					continue
				if not first:
					out.append(",")
				first = false
				out.append(_escape_json_string(k))
				out.append(":")
				var child_path: String = k if parent_path.is_empty() else (parent_path + "." + k)
				_serialize_value(d[k], child_path, out)
			out.append("}")
		_:
			out.append("null")


static func _escape_json_string(s: String) -> String:
	var res: String = "\""
	for i: int in range(s.length()):
		var code: int = s.unicode_at(i)
		match code:
			0x22:
				res += "\\\""
			0x5C:
				res += "\\\\"
			0x08:
				res += "\\b"
			0x0C:
				res += "\\f"
			0x0A:
				res += "\\n"
			0x0D:
				res += "\\r"
			0x09:
				res += "\\t"
			_:
				if code < 0x20:
					res += "\\u%04x" % code
				else:
					res += s[i]
	res += "\""
	return res
