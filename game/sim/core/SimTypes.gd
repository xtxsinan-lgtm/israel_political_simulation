class_name SimTypes
extends RefCounted

const CURRENT_SAVE_VERSION: int = 1
const MAX_ACTIVE_MODIFIERS: int = 400
const MAX_DELAYED_EFFECTS: int = 2000
const MAX_SCHEDULED_EVENTS: int = 500
const MAX_UI_QUEUE: int = 32
const MAX_ERROR_LOG: int = 500
const MONTHLY_SNAPSHOT_RING_SIZE: int = 12
const TOTAL_KNESSET_SEATS: int = 120

const AUTHORITATIVE_RNG_STREAMS: Array[String] = [
	"ai", "combat", "core", "economy", "elections",
	"events", "politics", "random_events", "world",
]
const COSMETIC_RNG_STREAM: String = "cosmetic"

const END_TENURE_PRIORITY: Dictionary = {
	"state_collapse": 12,
	"assassination": 11,
	"coup": 10,
	"death": 9,
	"overthrow": 8,
	"health_incapacity": 7,
	"primary_loss": 6,
	"no_confidence": 5,
	"coalition_failure": 4,
	"election_loss": 3,
	"resignation": 2,
	"player_quit": 1,
}

const KNOWN_MODIFIER_FACTORS: Dictionary = {
	"pc_income": true,
	"pc_cost": true,
	"covert_cost": true,
	"oratory_effect": true,
	"swing_sensitivity": true,
	"vote_attraction": true,
	"fiscal_spend": true,
	"fx_spend": true,
	"us_aid": true,
}

const STANCE_AXES: Array[String] = ["security", "economy", "religion", "territory", "democracy"]
