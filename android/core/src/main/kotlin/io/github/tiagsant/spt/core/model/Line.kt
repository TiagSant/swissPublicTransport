package io.github.tiagsant.spt.core.model

/** Transport modes, in the order lines are listed (trains first). Same codes and order as the prototype (US-11). */
enum class Mode(val key: String) {
    TRAIN("train"), METRO("metro"), TRAM("tram"), BUS("bus"), SHIP("ship"), FUNICULAR("funicular"), CABLEWAY("cableway"), OTHER("other");

    companion object {
        // API category codes → mode, validated against real data (docs/data/real-data-validation.md)
        private val CATEGORIES: List<Pair<Mode, Set<String>>> = listOf(
            METRO to setOf("M", "METRO"),
            TRAM to setOf("T", "TRAM", "NFT", "STR"),
            BUS to setOf("B", "BUS", "NFB", "BN", "EV", "KB", "EXB", "BP", "TX", "NB", "RUB", "CAR"),
            SHIP to setOf("BAT", "BAV", "FAE", "SCH", "SHIP"),
            FUNICULAR to setOf("FUN"),
            CABLEWAY to setOf("PB", "GB"),
            TRAIN to setOf(
                "S", "SN", "SL", "L", "R", "RE", "IR", "IRE", "IC", "ICE", "ICN", "EC", "EN", "NJ", "TGV",
                "TER", "RJ", "RJX", "PE", "EXT", "RB", "IN", "TRN",
            ),
        )

        // OJP `PtMode` → mode (the prototype's MODE_ICON)
        private val OJP_MODES = mapOf(
            "rail" to TRAIN, "tram" to TRAM, "bus" to BUS, "trolleyBus" to BUS, "coach" to BUS, "water" to SHIP,
            "ferry" to SHIP, "funicular" to FUNICULAR, "telecabin" to CABLEWAY, "cableway" to CABLEWAY, "metro" to METRO,
        )

        /** Mode of a category code ("T", "IR", "BAT"…); [OTHER] when unknown. */
        fun ofCategory(category: String?): Mode {
            val c = category.orEmpty().trim().uppercase()
            return CATEGORIES.firstOrNull { c in it.second }?.first ?: OTHER
        }

        /** Mode of an OJP `PtMode`, `null` when absent or unknown. */
        fun ofOjp(ptMode: String?): Mode? = OJP_MODES[ptMode]

        fun ofKey(key: String): Mode? = entries.firstOrNull { it.key == key }
    }
}

/** A transport company. [ref] is its number in the data (e.g. 881 = TPG); [name] is empty when unknown. */
data class Operator(val ref: String, val name: String)

/** Colours of a line badge, `#rrggbb` (filled in by US-70). */
data class LineColour(val background: String, val text: String)

/**
 * A line as the rider sees it on the street.
 *
 * [category] and [number] are the data's ("T" / "14", "IR" / "57", "R" / "L4"); [name] is the published name
 * ("14", "IR57", "RL4"). [label] is what the badge shows, with the prototype's rules.
 */
data class Line(
    val category: String,
    val number: String,
    val name: String,
    val operator: Operator? = null,
    val colour: LineColour? = null,
) {
    val mode: Mode get() = Mode.ofCategory(category)

    /** Badge text: "14", "m2", "L1", "IR 90", "IC" (a long number is a run number, not shown). */
    val label: String
        get() {
            val n = number.trim()
            val c = category.trim()
            return when (mode) {
                Mode.METRO -> if (DIGITS.matches(n)) "m$n" else n.ifEmpty { c }.ifEmpty { "?" }.replace(METRO_CODE, "m$1")
                Mode.TRAIN -> when {
                    n.firstOrNull()?.isLetter() == true && n.first().code < 128 -> n
                    n.isNotEmpty() && n.length <= 3 -> "$c $n".trim()
                    else -> c.ifEmpty { n }.ifEmpty { "?" }
                }
                else -> n.ifEmpty { c }.ifEmpty { "?" }
            }
        }

    /** Identity of the line on a board: mode and label (the prototype's `lineKey`). */
    val key: String get() = "${mode.key}|$label"

    private companion object {
        val DIGITS = Regex("""^\d+$""")
        val METRO_CODE = Regex("""^M(\d+)$""")
    }
}
