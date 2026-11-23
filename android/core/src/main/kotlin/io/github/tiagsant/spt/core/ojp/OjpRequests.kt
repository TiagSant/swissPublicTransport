package io.github.tiagsant.spt.core.ojp

import io.github.tiagsant.spt.core.model.PlaceType
import io.github.tiagsant.spt.core.model.SwissTime
import io.github.tiagsant.spt.core.model.Zone
import java.math.BigDecimal
import java.time.Instant

/**
 * Builders of OJP 2.0 requests. The XML is the same, byte for byte, as the prototype's `assets/ojp.js` builds
 * (checked on its recorded requests, `tests/fixtures/ojp-kotlin/requests`).
 *
 * [lang] is the answer's language (`fr`, `de`, `it`, `en`, `rm`); [now] the request timestamp.
 */
class OjpRequests(private val requestor: String = REQUESTOR) {

    /** Stops (and, with [types], addresses and places of interest) by name, optionally inside [zone]. */
    fun locationsByName(
        name: String,
        lang: String,
        now: Instant,
        limit: Int = 20,
        types: List<PlaceType> = listOf(PlaceType.STOP),
        zone: Zone? = null,
    ): String = envelope(
        "<OJPLocationInformationRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>" +
            "<InitialInput><Name>${esc(name)}</Name>${zone?.let(::rectangle).orEmpty()}</InitialInput>" +
            restrictions(limit, types) + "</OJPLocationInformationRequest>",
        lang, now,
    )

    /** Stops inside [zone] ("stops near me", around a map point). */
    fun locationsInZone(zone: Zone, lang: String, now: Instant, limit: Int = 20): String = envelope(
        "<OJPLocationInformationRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>" +
            "<InitialInput>${rectangle(zone)}</InitialInput>" +
            restrictions(limit, listOf(PlaceType.STOP)) + "</OJPLocationInformationRequest>",
        lang, now,
    )

    /**
     * Departures at [stopId] from [from]. [onward] `false` leaves out the next stops of each run: about 5× lighter,
     * used for refreshes (the next stops are then rebuilt from [RunPatterns]).
     */
    fun stopEvents(
        stopId: String,
        from: Instant,
        lang: String,
        now: Instant,
        limit: Int = 40,
        onward: Boolean = true,
    ): String = envelope(
        "<OJPStopEventRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>" +
            "<Location><PlaceRef><siri:StopPointRef>${esc(stopId)}</siri:StopPointRef><Name><Text>n/a</Text></Name></PlaceRef>" +
            "<DepArrTime>${SwissTime.isoMillis(from)}</DepArrTime></Location>" +
            "<Params><IncludeAllRestrictedLines>true</IncludeAllRestrictedLines>" +
            "<NumberOfResults>$limit</NumberOfResults><StopEventType>departure</StopEventType>" +
            "<IncludePreviousCalls>false</IncludePreviousCalls><IncludeOnwardCalls>$onward</IncludeOnwardCalls>" +
            "<UseRealtimeData>explanatory</UseRealtimeData></Params></OJPStopEventRequest>",
        lang, now,
    )

    /** Journeys between two stops, leaving at [at] or, with [arrive], arriving by [at]. */
    fun trip(
        fromId: String,
        toId: String,
        at: Instant,
        lang: String,
        now: Instant,
        arrive: Boolean = false,
        limit: Int = 4,
    ): String {
        val t = "<DepArrTime>${SwissTime.isoMillis(at)}</DepArrTime>"
        fun place(id: String) = "<PlaceRef><StopPlaceRef>${esc(id)}</StopPlaceRef><Name><Text>n/a</Text></Name></PlaceRef>"
        return envelope(
            "<OJPTripRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>" +
                "<Origin>${place(fromId)}${if (arrive) "" else t}</Origin>" +
                "<Destination>${place(toId)}${if (arrive) t else ""}</Destination>" +
                "<Params><NumberOfResults>$limit</NumberOfResults><UseRealtimeData>explanatory</UseRealtimeData>" +
                "<IncludeAllRestrictedLines>true</IncludeAllRestrictedLines><IncludeTrackSections>false</IncludeTrackSections>" +
                "<IncludeLegProjection>false</IncludeLegProjection><IncludeIntermediateStops>true</IncludeIntermediateStops></Params>" +
                "</OJPTripRequest>",
            lang, now,
        )
    }

    private fun envelope(inner: String, lang: String, now: Instant): String {
        val ts = SwissTime.isoMillis(now)
        return "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" +
            "<OJP xmlns=\"http://www.vdv.de/ojp\" xmlns:siri=\"http://www.siri.org.uk/siri\" version=\"2.0\">" +
            "<OJPRequest><siri:ServiceRequest>" +
            "<siri:ServiceRequestContext><siri:Language>${esc(lang)}</siri:Language></siri:ServiceRequestContext>" +
            "<siri:RequestTimestamp>$ts</siri:RequestTimestamp><siri:RequestorRef>$requestor</siri:RequestorRef>" +
            inner.replaceFirst("{TS}", ts) +
            "</siri:ServiceRequest></OJPRequest></OJP>"
    }

    private fun rectangle(z: Zone) =
        "<GeoRestriction><Rectangle>" +
            "<UpperLeft><siri:Longitude>${num(z.lonMin)}</siri:Longitude><siri:Latitude>${num(z.latMax)}</siri:Latitude></UpperLeft>" +
            "<LowerRight><siri:Longitude>${num(z.lonMax)}</siri:Longitude><siri:Latitude>${num(z.latMin)}</siri:Latitude></LowerRight>" +
            "</Rectangle></GeoRestriction>"

    private fun restrictions(limit: Int, types: List<PlaceType>) =
        "<Restrictions>${types.joinToString("") { "<Type>${it.ojp}</Type>" }}<NumberOfResults>$limit</NumberOfResults>" +
            "<IncludePtModes>true</IncludePtModes></Restrictions>"

    companion object {
        const val ENDPOINT = "https://api.opentransportdata.swiss/ojp20"
        const val REQUESTOR = "swissPublicTransport"

        /** XML escaping of text and attribute values. */
        fun esc(s: String): String = buildString(s.length) {
            for (c in s) when (c) {
                '<' -> append("&lt;")
                '>' -> append("&gt;")
                '&' -> append("&amp;")
                '\'' -> append("&apos;")
                '"' -> append("&quot;")
                else -> append(c)
            }
        }

        /** A number as JavaScript prints it: `46.0` → `46`, `6.0833` → `6.0833`, never in exponent form. */
        fun num(d: Double): String {
            require(d.isFinite()) { "not a number: $d" }
            val plain = BigDecimal.valueOf(d).stripTrailingZeros().toPlainString()
            return if (plain == "-0") "0" else plain
        }
    }
}
