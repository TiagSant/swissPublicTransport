package io.github.tiagsant.spt.core.model

import java.time.Duration
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException

/**
 * Time of a stop event: the timetable's, and the live estimate when the operator sends one.
 * Without live data the event follows its scheduled time (as in the prototype, #19).
 */
data class EventTime(val scheduled: Instant, val estimated: Instant? = null) {
    /** Real-time data exists for this event. */
    val live: Boolean get() = estimated != null

    /** The time to show and to compute with: live when known, otherwise scheduled. */
    val time: Instant get() = estimated ?: scheduled

    /** Delay in whole minutes, rounded as the prototype (`Math.round`); 0 without live data, negative when early. */
    val delayMinutes: Int
        get() = estimated?.let { Math.round(Duration.between(scheduled, it).toMillis() / 60_000.0).toInt() } ?: 0

    companion object {
        /** When the data gives only a delay in minutes (transport.opendata.ch style). */
        fun withDelay(scheduled: Instant, delayMinutes: Int): EventTime =
            EventTime(scheduled, scheduled.plus(Duration.ofMinutes(delayMinutes.toLong())))
    }
}

/** Planned platform, and the live one when announced. */
data class Platform(val planned: String? = null, val estimated: String? = null) {
    /** The platform to show: the live one first. */
    val shown: String? get() = estimated ?: planned

    /** The platform was changed in the live data. */
    val changed: Boolean get() = estimated != null && planned != null && estimated != planned

    companion object {
        val NONE = Platform()
    }
}

/** Swiss local time. Every time shown to the rider is in Europe/Zurich, whatever the phone's zone. */
object SwissTime {
    val ZONE: ZoneId = ZoneId.of("Europe/Zurich")

    private val HHMM = DateTimeFormatter.ofPattern("HH:mm")
    private val API_DATE_TIME = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
    private val ISO_MILLIS = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'").withZone(ZoneOffset.UTC)
    private val COMPACT_OFFSET = Regex("""([+-]\d{2})(\d{2})$""")

    fun local(instant: Instant): ZonedDateTime = instant.atZone(ZONE)

    /** "07:05" in Swiss time. */
    fun hhmm(instant: Instant): String = HHMM.format(local(instant))

    /** "2026-11-20 07:05" in Swiss time (the format of transport.opendata.ch's `datetime`). */
    fun apiDateTime(instant: Instant): String = API_DATE_TIME.format(local(instant))

    /** "2026-11-20T06:05:00.000Z": UTC with milliseconds, as JavaScript's `toISOString()` (OJP requests). */
    fun isoMillis(instant: Instant): String = ISO_MILLIS.format(instant)

    /**
     * Reads the times found in the data: `2026-11-16T06:57:00Z`, `2026-11-16T07:55:40.4294405+01:00`,
     * or `2026-11-16T07:57:00+0100` (offset without a colon, as the prototype's `parseTime`). `null` when unreadable.
     */
    fun parse(text: String?): Instant? {
        val s = text?.trim().orEmpty()
        if (s.isEmpty()) return null
        return try {
            OffsetDateTime.parse(s.replace(COMPACT_OFFSET, "$1:$2")).toInstant()
        } catch (_: DateTimeParseException) {
            try {
                Instant.parse(s)
            } catch (_: DateTimeParseException) {
                null
            }
        }
    }
}
