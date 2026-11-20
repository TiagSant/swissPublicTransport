package io.github.tiagsant.spt.core.model

import java.time.Duration
import java.time.Instant

/** A stop of a ride: the stop, its arrival and departure times (absent at the first and last stop) and platform. */
data class Call(
    val stop: Stop,
    val arrival: EventTime? = null,
    val departure: EventTime? = null,
    val platform: Platform = Platform.NONE,
)

/** One part of a journey. */
sealed interface Leg

/**
 * A ride in one vehicle, from its first call (boarding) to its last (getting off), every stop in between included.
 * [cancelled]: the run, or its stop where the rider boards or gets off, is cancelled in the live data (US-61).
 */
data class Ride(
    val line: Line,
    val destination: String,
    val calls: List<Call>,
    val cancelled: Boolean = false,
    val multiDestination: Boolean = false,
    val messages: List<TrafficMessage> = emptyList(),
) : Leg {
    init {
        require(calls.size >= 2) { "a ride has a boarding and a getting-off stop" }
    }

    val board: Call get() = calls.first()
    val alight: Call get() = calls.last()
    val departure: EventTime? get() = board.departure
    val arrival: EventTime? get() = alight.arrival
    val intermediate: List<Call> get() = calls.subList(1, calls.size - 1)
}

/** A walk: a change on foot between stops, or to / from a place. [duration] as planned by the data. */
data class Walk(val from: Place, val to: Place, val duration: Duration?) : Leg

/** Time spent waiting at [at] before the next ride. */
data class Wait(val at: Stop, val from: Instant, val until: Instant) : Leg {
    val duration: Duration get() = Duration.between(from, until)
}

/** A journey as the data plans it: rides and walks, in order. */
data class Journey(val legs: List<Leg>, val duration: Duration? = null, val transfers: Int = 0) {
    val rides: List<Ride> get() = legs.filterIsInstance<Ride>()

    /** First departure and last arrival of a ride (live when known). */
    val departure: Instant? get() = rides.firstOrNull()?.departure?.time
    val arrival: Instant? get() = rides.lastOrNull()?.arrival?.time

    /** Some ride of the journey is cancelled. */
    val cancelled: Boolean get() = rides.any { it.cancelled }

    /** Minutes on foot planned by the data. */
    val walking: Duration get() = legs.filterIsInstance<Walk>().fold(Duration.ZERO) { acc, w -> acc + (w.duration ?: Duration.ZERO) }

    /**
     * The legs with the waits made explicit: between two rides, the time left once the walks between them are done,
     * spent at the stop of the next ride. Live times are used when known.
     */
    fun withWaits(): List<Leg> {
        val out = mutableListOf<Leg>()
        var lastArrival: Instant? = null
        var walked = Duration.ZERO
        for (leg in legs) {
            when (leg) {
                is Walk -> walked += leg.duration ?: Duration.ZERO
                is Ride -> {
                    val dep = leg.departure?.time
                    if (lastArrival != null && dep != null) {
                        val start = lastArrival + walked
                        if (start < dep) out += Wait(leg.board.stop, start, dep)
                    }
                    lastArrival = leg.arrival?.time
                    walked = Duration.ZERO
                }
                is Wait -> Unit
            }
            if (leg !is Wait) out += leg
        }
        return out
    }
}
