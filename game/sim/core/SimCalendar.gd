class_name SimCalendar
extends RefCounted


static func is_leap_year(y: int) -> bool:
	return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


static func days_in_month(y: int, m: int) -> int:
	if m == 1 or m == 3 or m == 5 or m == 7 or m == 8 or m == 10 or m == 12:
		return 31
	if m == 4 or m == 6 or m == 9 or m == 11:
		return 30
	if m == 2:
		return 29 if is_leap_year(y) else 28
	return 30


static func days_from_civil(y: int, m: int, d: int) -> int:
	var y_adj: int = y - (1 if m <= 2 else 0)
	var era: int = SimMath.idiv_floor(y_adj, 400)
	var yoe: int = y_adj - era * 400
	var mp: int = m + (-3 if m > 2 else 9)
	var doy: int = SimMath.idiv_floor(153 * mp + 2, 5) + d - 1
	var doe: int = yoe * 365 + SimMath.idiv_floor(yoe, 4) - SimMath.idiv_floor(yoe, 100) + doy
	return era * 146097 + doe - 719468


static func civil_from_days(z: int) -> Vector3i:
	var z_adj: int = z + 719468
	var era: int = SimMath.idiv_floor(z_adj, 146097)
	var doe: int = z_adj - era * 146097
	var yoe: int = SimMath.idiv_floor(
		doe - SimMath.idiv_floor(doe, 1460) + SimMath.idiv_floor(doe, 36524) - SimMath.idiv_floor(doe, 146096),
		365
	)
	var y: int = yoe + era * 400
	var doy: int = doe - (365 * yoe + SimMath.idiv_floor(yoe, 4) - SimMath.idiv_floor(yoe, 100))
	var mp: int = SimMath.idiv_floor(5 * doy + 2, 153)
	var d: int = doy - SimMath.idiv_floor(153 * mp + 2, 5) + 1
	var m: int = mp + (3 if mp < 10 else -9)
	if m <= 2:
		y += 1
	return Vector3i(y, m, d)


static func parse_ymd(date_str: String) -> Vector3i:
	var parts: PackedStringArray = date_str.strip_edges().split("-")
	var y: int = int(parts[0]) if parts.size() > 0 else 1970
	var m: int = int(parts[1]) if parts.size() > 1 else 1
	var d: int = int(parts[2]) if parts.size() > 2 else 1
	return Vector3i(y, m, d)


static func format_ymd(y: int, m: int, d: int) -> String:
	return "%04d-%02d-%02d" % [y, m, d]


static func date_to_abs_day(date_str: String) -> int:
	var ymd: Vector3i = parse_ymd(date_str)
	return days_from_civil(ymd.x, ymd.y, ymd.z)


static func abs_day_to_date(abs_d: int) -> String:
	var ymd: Vector3i = civil_from_days(abs_d)
	return format_ymd(ymd.x, ymd.y, ymd.z)


static func weekday_from_abs_day(abs_d: int) -> int:
	return posmod(abs_d + 3, 7)


static func is_week(weekday: int) -> bool:
	return weekday == 6


static func is_month(d: int) -> bool:
	return d == 1


static func is_quarter(m: int, d: int) -> bool:
	return d == 1 and (m == 1 or m == 4 or m == 7 or m == 10)


static func is_half_year(m: int, d: int) -> bool:
	return d == 1 and (m == 1 or m == 7)


static func is_year(m: int, d: int) -> bool:
	return m == 1 and d == 1


static func is_first_sunday_of_month(weekday: int, d: int) -> bool:
	return weekday == 6 and d <= 7


static func compute_era(y: int, m: int) -> int:
	if y <= 1955:
		return 1
	if y < 1967 or (y == 1967 and m < 6):
		return 2
	if y < 1977 or (y == 1977 and m < 6):
		return 3
	if y < 1992 or (y == 1992 and m < 7):
		return 4
	return 5


static func months_since(current_day_index: int, ref_day_index: int) -> int:
	if ref_day_index < 0:
		return 9999
	return SimMath.idiv_floor(maxi(0, current_day_index - ref_day_index), 30)


static func days_since(current_day_index: int, ref_day_index: int) -> int:
	if ref_day_index < 0:
		return 999999
	return maxi(0, current_day_index - ref_day_index)


static func verify_t02_calendar_vectors() -> bool:
	if date_to_abs_day("1977-06-20") != 2727:
		return false
	if weekday_from_abs_day(2727) != 0:
		return false
	if weekday_from_abs_day(2733) != 6:
		return false
	if abs_day_to_date(2727) != "1977-06-20":
		return false
	if not is_week(6) or is_week(0):
		return false
	if not is_month(1) or is_month(20):
		return false
	if not is_quarter(7, 1) or is_quarter(6, 1):
		return false
	if not is_year(1, 1) or is_year(6, 20):
		return false
	if compute_era(1977, 6) != 4:
		return false
	if compute_era(1977, 5) != 3:
		return false
	if months_since(60, 0) != 2:
		return false
	if months_since(10, -1) != 9999:
		return false
	if days_since(12, -5) != 999999:
		return false
	if days_since(12, 5) != 7:
		return false
	if not is_first_sunday_of_month(6, 3):
		return false
	if not is_leap_year(1976) or is_leap_year(1977):
		return false
	if days_in_month(1977, 2) != 28 or days_in_month(1976, 2) != 29:
		return false
	return true
