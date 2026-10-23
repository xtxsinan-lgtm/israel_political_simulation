/* Port of game/ui/components/FuzzyBand.gd (D-088 fog of war). */
export const FUZZY_PARAMS = new Set([
  "health", "coup_risk", "assassination_risk", "regime_stability", "country_war_readiness", "war_probability",
  "faction_strength", "faction_legitimacy", "faction_moderation", "faction_cohesion", "uprising_risk",
  "complacency", "nuclear_progress", "nuclear_exposure_risk", "enemy_nuclear_progress", "islamic_assoc_strength",
]);
/* National (unscoped) fuzzy params shown in the ledger (SimReadonlySnapshot.fuzzy_bands). */
export const LEDGER_FUZZY = [
  "assassination_risk", "complacency", "coup_risk", "islamic_assoc_strength",
  "nuclear_exposure_risk", "nuclear_progress", "uprising_risk",
];

const RISK_WORDS = ["轻微", "可控", "值得警惕", "高企", "严峻"];
const HEALTH_WORDS = ["垂危", "欠佳", "一般", "良好", "硬朗"];
const STRENGTH_WORDS = ["极弱", "偏弱", "中等", "偏强", "极强"];

export const FuzzyBand = {
  isFuzzy(paramId) { return FUZZY_PARAMS.has(paramId); },
  bandIndex(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return -1;
    const v = Math.min(100, Math.max(0, Number(value)));
    return Math.min(4, Math.floor(v / 20));
  },
  bandLow(band) { return band * 20; },
  bandHigh(band) { return band * 20 + 20; },
  bandCentre(band) { return band * 20 + 10; },
  words(paramId = "") {
    if (paramId === "health") return HEALTH_WORDS;
    if (paramId === "" || /risk|probability|readiness|progress|complacency|exposure/.test(paramId)) return RISK_WORDS;
    return STRENGTH_WORDS;
  },
  bandWord(band, paramId = "") { return band < 0 ? "情报不足" : this.words(paramId)[band]; },
  rangeText(band) { return `${this.bandLow(band)}%\u2013${this.bandHigh(band)}%`; },
  describeBand(band, paramId = "") {
    if (band < 0) return "情报不足";
    return `${this.bandWord(band, paramId)} (${this.rangeText(band)})`;
  },
  describe(value, paramId = "") { return this.describeBand(this.bandIndex(value), paramId); },
  /* display(id, v, fmt): band text for fuzzy params, else the number with `digits` decimals. */
  display(paramId, value, digits = 1) {
    if (this.isFuzzy(paramId)) return this.describe(value, paramId);
    return Number(value ?? 0).toFixed(digits);
  },
};
