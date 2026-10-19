extends SceneTree


func _initialize() -> void:
	quit(_run())


func _run() -> int:
	var registry: GameData = GameData.new()
	if registry.load_all_runtime_data() != OK:
		return _fail("load")
	var state: SimState = SimState.new()
	state.init_from_scenario_bundle("begin_1977", 19770620, false)
	state.run["headless"] = true
	state.run["perf_bench"] = true
	var scheduler: DailyScheduler = DailyScheduler.new()
	var daily_ms: Array[float] = []
	var monthly_ms: Array[float] = []
	var year_sums: Array[float] = []
	var year_counts: Array[int] = []
	year_sums.resize(30)
	year_counts.resize(30)
	for year: int in range(30):
		year_sums[year] = 0.0
		year_counts[year] = 0
	var days_run: int = 0
	for day: int in range(10950):
		var started: int = Time.get_ticks_usec()
		var stepped: Dictionary = scheduler.execute_day(state)
		var _snap: SimReadonlySnapshot = SimReadonlySnapshot.capture(state)
		var elapsed: float = float(Time.get_ticks_usec() - started) / 1000.0
		days_run += 1
		var year: int = mini(SimMath.idiv_floor(day, 365), 29)
		year_sums[year] = float(year_sums[year]) + elapsed
		year_counts[year] = int(year_counts[year]) + 1
		if state.clock.is_month:
			monthly_ms.append(elapsed)
		else:
			daily_ms.append(elapsed)
		if bool(stepped.get("ended", false)):
			break
	if days_run < 10950:
		return _fail("run ended after %d days (phase=%s); the 30-year bench needs 10950" % [days_run, state.run.get("phase", "")])
	for y: int in range(30):
		if int(year_counts[y]) == 0:
			return _fail("empty year bucket %d" % y)
	var avg_daily: float = _avg(daily_ms)
	var p99_monthly: float = _p99(monthly_ms)
	var year1: float = float(year_sums[0]) / float(maxi(int(year_counts[0]), 1))
	var year30: float = float(year_sums[29]) / float(maxi(int(year_counts[29]), 1))
	var ratio: float = year30 / maxf(year1, 0.001)
	print("PERF daily_ms=%s monthly_p99=%s R=%s days=%s" % [avg_daily, p99_monthly, ratio, state.clock.day_index])
	if avg_daily >= 5.0 or p99_monthly >= 16.0 or ratio > 1.30:
		return _fail("budget")
	print("PERF_BENCH_30Y_PASSED")
	return 0


func _avg(values: Array[float]) -> float:
	if values.is_empty():
		return 0.0
	var total: float = 0.0
	for i: int in range(values.size()):
		total += values[i]
	return total / float(values.size())


func _p99(values: Array[float]) -> float:
	if values.is_empty():
		return 0.0
	values.sort()
	var index: int = mini(values.size() - 1, SimMath.round_half_up_int(float(values.size() - 1) * 0.99))
	return values[index]


func _fail(message: String) -> int:
	push_error(message)
	print("PERF_FAIL %s" % message)
	return 1
