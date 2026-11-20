package io.github.tiagsant.spt.core.model

import java.time.Instant

/** A validity period of a traffic message; an open end is `null`. */
data class Period(val start: Instant?, val end: Instant?) {
    operator fun contains(t: Instant) = (start == null || start <= t) && (end == null || t <= end)
}

/**
 * A traffic message (SIRI SX situation, US-67), in the app's language when the data has it.
 * Shown only for a ride within one of its [periods] (all the time when it has none).
 */
data class TrafficMessage(
    val id: String,
    val severity: String = "normal",
    val planned: Boolean = false,
    val periods: List<Period> = emptyList(),
    val summary: String = "",
    val description: String = "",
    val consequence: String = "",
    val recommendation: String = "",
    val duration: String = "",
) {
    fun isValidAt(t: Instant): Boolean = periods.isEmpty() || periods.any { t in it }
}

/** The messages valid at [t] (the prototype's `activeSits`). */
fun List<TrafficMessage>.validAt(t: Instant): List<TrafficMessage> = filter { it.isValidAt(t) }
