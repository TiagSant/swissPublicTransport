package io.github.tiagsant.spt.core.model

import java.time.Instant

/** A stop further on a run, with the time it is reached (live when known) and its platform. */
data class NextStop(
    val stop: Stop,
    val arrival: Instant?,
    val departure: Instant? = null,
    val platform: String? = null,
) {
    /** The time to show: arrival, or departure at the first stop. */
    val time: Instant? get() = arrival ?: departure
}

/**
 * A departure on a stop's board. Cancelled runs and stops not served are left out of boards, as in the prototype.
 *
 * [runPattern] groups runs that serve the same next stops (line, direction, terminus stop); it lets a light board
 * refresh (without next stops) rebuild them from an earlier full answer.
 */
data class Departure(
    val line: Line,
    val destination: String,
    val stop: Stop,
    val time: EventTime,
    val platform: Platform = Platform.NONE,
    val nextStops: List<NextStop> = emptyList(),
    val multiDestination: Boolean = false,
    val messages: List<TrafficMessage> = emptyList(),
    val runPattern: String = "",
) {
    /**
     * Direction of the departure: its line and the next stop after this one, or its terminus when the next stops
     * are not known (the prototype's `dirKey`, the unit of the rider's habits).
     */
    val directionKey: String
        get() {
            val next = nextStops.firstOrNull { it.stop.name.isNotEmpty() && it.stop.id != stop.id }
            return line.key + ">" + (next?.let { it.stop.id.ifEmpty { it.stop.name } } ?: "to:$destination")
        }

    /** Messages valid at the departure's scheduled time. */
    val validMessages: List<TrafficMessage> get() = messages.validAt(time.scheduled)
}

/**
 * A stop's departures. [unknownPatterns] counts departures of a light answer whose next stops could not be rebuilt;
 * [notice] is the data's message when it answered without results ("no results", etc.).
 */
data class Board(
    val stop: Stop,
    val departures: List<Departure>,
    val unknownPatterns: Int = 0,
    val notice: String? = null,
)
