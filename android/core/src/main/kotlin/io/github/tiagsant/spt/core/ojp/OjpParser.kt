package io.github.tiagsant.spt.core.ojp

import io.github.tiagsant.spt.core.model.Board
import io.github.tiagsant.spt.core.model.Call
import io.github.tiagsant.spt.core.model.Departure
import io.github.tiagsant.spt.core.model.EventTime
import io.github.tiagsant.spt.core.model.GeoPoint
import io.github.tiagsant.spt.core.model.Journey
import io.github.tiagsant.spt.core.model.Leg
import io.github.tiagsant.spt.core.model.Line
import io.github.tiagsant.spt.core.model.Mode
import io.github.tiagsant.spt.core.model.NextStop
import io.github.tiagsant.spt.core.model.Operator
import io.github.tiagsant.spt.core.model.Period
import io.github.tiagsant.spt.core.model.Place
import io.github.tiagsant.spt.core.model.Platform
import io.github.tiagsant.spt.core.model.Ride
import io.github.tiagsant.spt.core.model.Stop
import io.github.tiagsant.spt.core.model.StopIds
import io.github.tiagsant.spt.core.model.SwissTime
import io.github.tiagsant.spt.core.model.TrafficMessage
import io.github.tiagsant.spt.core.model.Walk
import io.github.tiagsant.spt.core.ojp.Xml.all
import io.github.tiagsant.spt.core.ojp.Xml.el
import io.github.tiagsant.spt.core.ojp.Xml.kids
import io.github.tiagsant.spt.core.ojp.Xml.lang
import io.github.tiagsant.spt.core.ojp.Xml.txt
import org.w3c.dom.Document
import org.w3c.dom.Element
import java.time.Duration
import java.time.Instant
import java.time.format.DateTimeParseException

/** Stops found by a location search, and the data's notice when it found nothing. */
data class StopSearchResult(val stops: List<Stop>, val notice: String? = null)

/** Stops, addresses and places of interest found by a location search (US-23). */
data class PlaceSearchResult(val places: List<Place>, val notice: String? = null)

/** Journeys found by a trip request. */
data class TripResult(val journeys: List<Journey>, val notice: String? = null)

/**
 * Reads OJP 2.0 answers into the domain model, with the rules of the prototype's `assets/ojp.js`
 * (checked on every recorded answer, `tests/fixtures/ojp-kotlin/answers`).
 *
 * Answers that say "no results" (HTTP 200 with an `ErrorCondition`) give an empty result with a notice.
 * Unreadable XML throws [OjpException.Malformed].
 */
object OjpParser {
    // Operators seen in Geneva answers (siri:OperatorRef "ojp:<number>"); others keep an empty name (US-70 adds more)
    private val OPERATORS = mapOf("881" to "TPG", "11" to "SBB", "199" to "Mouettes genevoises", "1185" to "SNCF")

    // OJP mode → category code understood by the app (same codes as transport.opendata.ch)
    private val MODE_CATEGORY = mapOf(
        "tram" to "T", "bus" to "B", "trolleyBus" to "B", "coach" to "B", "water" to "BAT", "ferry" to "BAT",
        "funicular" to "FUN", "telecabin" to "GB", "cableway" to "PB", "metro" to "M",
    )
    private val TRAIN_NAME = Regex("""^([A-Z]+?)(L\d+|\d+)$""")
    private val TRAILING_NUMBER = Regex("""(\d+)$""")
    private val WHITESPACE = Regex("""\s+""")
    private const val NOTICE_MAX = 200
    private const val PATTERN_STOPS = 8

    /** "IR57" → IR / 57, "RL4" (Léman Express) → R / L4, "RE33" → RE / 33, "TGV" → TGV / "". */
    fun splitTrainName(name: String): Pair<String, String> {
        val m = TRAIN_NAME.find(name.replace(WHITESPACE, "")) ?: return name to ""
        return m.groupValues[1] to m.groupValues[2]
    }

    // ---------- Location information ----------

    /** Stops of a location answer (addresses and places of interest left out). */
    fun stops(xml: String): StopSearchResult {
        val doc = Xml.parse(xml)
        val stops = doc.all("PlaceResult").mapNotNull { r ->
            val place = r.el("Place")
            val sp = place.el("StopPlace") ?: return@mapNotNull null
            val id = StopIds.fromOjp(sp.txt("StopPlaceRef")) ?: return@mapNotNull null
            Stop(id, sp.txt("StopPlaceName").ifEmpty { place.txt("Name") }, geo(place), mode = Mode.ofOjp(place.txt("Mode/PtMode")))
        }
        return StopSearchResult(stops, notice(doc))
    }

    /** Stops, addresses and places of interest; building entrances ("60.1") dropped when the main number is there. */
    fun places(xml: String): PlaceSearchResult {
        val doc = Xml.parse(xml)
        val out = ArrayList<Place>()
        for (r in doc.all("PlaceResult")) {
            val place = r.el("Place")
            val position = geo(place)
            val sp = place.el("StopPlace")
            val ad = place.el("Address")
            val poi = place.el("PointOfInterest")
            when {
                sp != null -> {
                    val id = StopIds.fromOjp(sp.txt("StopPlaceRef")) ?: continue
                    out += Place.StopPlace(
                        Stop(id, sp.txt("StopPlaceName").ifEmpty { place.txt("Name") }, position, mode = Mode.ofOjp(place.txt("Mode/PtMode"))),
                    )
                }
                ad != null && position != null -> out += Place.Address(
                    ad.txt("Name").ifEmpty { place.txt("Name") }, position,
                    street = ad.txt("Street"), houseNumber = ad.txt("HouseNumber"), town = ad.txt("TopographicPlaceName"),
                )
                poi != null && position != null ->
                    out += Place.PointOfInterest(poi.txt("PointOfInterestName").ifEmpty { place.txt("Name") }, position)
            }
        }
        fun Place.Address.key(number: String) = "$street|$number|$town"
        val mains = out.filterIsInstance<Place.Address>()
            .filter { it.houseNumber.isNotEmpty() && '.' !in it.houseNumber }
            .mapTo(HashSet()) { it.key(it.houseNumber) }
        val kept = out.filterNot { it is Place.Address && '.' in it.houseNumber && it.key(it.houseNumber.substringBefore('.')) in mains }
        return PlaceSearchResult(kept, notice(doc))
    }

    // ---------- Stop events ----------

    /**
     * A stop's board. A full answer (with onward calls) fills [patterns] with each run pattern's next stops; a light
     * answer (without) uses them to rebuild the next stops. [stopId] is the app id the board was asked for.
     */
    fun board(xml: String, stopId: String, patterns: RunPatterns? = null, lang: String = ""): Board {
        val doc = Xml.parse(xml)
        val places = contextPlaces(doc)
        val sits = situations(doc, lang)
        val departures = ArrayList<Departure>()
        var unknown = 0
        for (ev in doc.all("StopEvent")) {
            val call = ev.el("ThisCall/CallAtStop") ?: continue
            val service = ev.el("Service") ?: continue
            if (call.txt("NotServicedStop") == "true" || service.txt("Cancelled") == "true") continue
            val info = serviceInfo(service)
            val depPlanned = time(call, "ServiceDeparture", "TimetabledTime") ?: continue
            val depEstimated = time(call, "ServiceDeparture", "EstimatedTime")
            val ref = call.txt("StopPointRef")
            val hereId = StopIds.fromOjp(ref) ?: stopId
            val hereName = station(ref, call.txt("StopPointName"), places).name
            val onward = ev.kids("OnwardCall").mapNotNull { it.el("CallAtStop") }
            val next: List<NextStop>
            if (onward.isNotEmpty()) {
                val calls = onward.map { c ->
                    val aPlanned = time(c, "ServiceArrival", "TimetabledTime")
                    val dPlanned = time(c, "ServiceDeparture", "TimetabledTime")
                    val stop = station(c.txt("StopPointRef"), c.txt("StopPointName"), places)
                    val platform = c.txt("EstimatedQuay").ifEmpty { c.txt("PlannedQuay") }.ifEmpty { null }
                    val pattern = (aPlanned ?: dPlanned)?.let { PatternStop(stop.id, stop.name, Duration.between(depPlanned, it), stop.position, platform) }
                        ?: PatternStop(stop.id, stop.name, null, stop.position, platform)
                    NextStop(
                        stop,
                        arrival = time(c, "ServiceArrival", "EstimatedTime") ?: aPlanned,
                        departure = time(c, "ServiceDeparture", "EstimatedTime") ?: dPlanned,
                        platform = platform,
                    ) to pattern
                }
                next = calls.map { it.first }
                patterns?.set(info.pattern, calls.map { it.second }.filter { it.id != hereId }.take(PATTERN_STOPS))
            } else {
                val known = patterns?.get(info.pattern)
                if (known == null) unknown++
                val base = depEstimated ?: depPlanned
                next = known.orEmpty().map { p ->
                    NextStop(Stop(p.id, p.name, p.position), arrival = p.offset?.let { base + it }, platform = p.platform)
                }
            }
            departures += Departure(
                line = info.line,
                destination = info.to,
                stop = Stop(hereId, hereName),
                time = EventTime(depPlanned, depEstimated),
                platform = Platform(call.txt("PlannedQuay").ifEmpty { null }, call.txt("EstimatedQuay").ifEmpty { null }),
                nextStops = next,
                multiDestination = info.multiDestination,
                messages = situationsOf(listOf(service, ev), sits),
                runPattern = info.pattern,
            )
        }
        val st = places[StopIds.toSloid(stopId)]
        val name = st?.name?.ifEmpty { null } ?: departures.firstOrNull()?.stop?.name.orEmpty()
        return Board(Stop(stopId, name, st?.position), departures, unknown, notice(doc))
    }

    // ---------- Trips ----------

    fun trips(xml: String, lang: String = ""): TripResult {
        val doc = Xml.parse(xml)
        val places = contextPlaces(doc)
        val sits = situations(doc, lang)
        val journeys = ArrayList<Journey>()
        for (trip in doc.all("Trip")) {
            val legs = ArrayList<Leg>()
            for (leg in trip.kids("Leg")) {
                val timed = leg.el("TimedLeg")
                if (timed != null) {
                    val board = timed.el("LegBoard")
                    val alight = timed.el("LegAlight")
                    val service = timed.el("Service")
                    if (board == null || alight == null || service == null) throw OjpException.Malformed("timed leg without board, alight or service")
                    val info = serviceInfo(service)
                    val calls = (listOf(board) + timed.kids("LegIntermediate") + alight).map { c ->
                        Call(
                            station(c.txt("StopPointRef"), c.txt("StopPointName"), places),
                            arrival = eventTime(c, "ServiceArrival"),
                            departure = eventTime(c, "ServiceDeparture"),
                            platform = Platform(c.txt("PlannedQuay").ifEmpty { null }, c.txt("EstimatedQuay").ifEmpty { null }),
                        )
                    }
                    legs += Ride(
                        line = info.line,
                        destination = info.to,
                        calls = calls,
                        cancelled = service.txt("Cancelled") == "true" || board.txt("NotServicedStop") == "true" ||
                            alight.txt("NotServicedStop") == "true",
                        multiDestination = info.multiDestination,
                        messages = situationsOf(listOf(service, timed), sits),
                    )
                } else {
                    // TransferLeg (change on foot) or ContinuousLeg (walk to / from a place)
                    val w = leg.el("TransferLeg") ?: leg.el("ContinuousLeg") ?: continue
                    fun end(n: Element?): Place {
                        val ref = n.txt("StopPointRef").ifEmpty { n.txt("StopPlaceRef") }
                        val name = n.txt("Name")
                        return if (ref.isNotEmpty()) Place.StopPlace(station(ref, name, places)) else Place.Point(name, geo(n))
                    }
                    legs += Walk(end(w.el("LegStart")), end(w.el("LegEnd")), duration(w.txt("Duration").ifEmpty { leg.txt("Duration") }))
                }
            }
            if (legs.isNotEmpty()) journeys += Journey(legs, duration(trip.txt("Duration")), trip.txt("Transfers").toIntOrNull() ?: 0)
        }
        return TripResult(journeys, notice(doc))
    }

    // ---------- Shared pieces ----------

    private class ServiceInfo(val line: Line, val to: String, val multiDestination: Boolean, val pattern: String)

    private fun serviceInfo(service: Element): ServiceInfo {
        val mode = service.txt("Mode/PtMode")
        val name = service.txt("PublishedServiceName").ifEmpty { service.txt("PublicCode") }
        val (category, number) = if (mode == "rail") splitTrainName(name)
        else (MODE_CATEGORY[mode] ?: service.txt("ProductCategory/ShortName").ifEmpty { service.txt("Mode/ShortName") }) to name
        val opRef = TRAILING_NUMBER.find(service.txt("OperatorRef"))?.value
        return ServiceInfo(
            line = Line(category, number, name, opRef?.let { Operator(it, OPERATORS[it].orEmpty()) }),
            to = service.txt("DestinationText"),
            // US-54: "train with several destinations" (HRDF attribute A__FL): coupled trains that split on the way
            multiDestination = service.kids("Attribute").any { it.txt("Code") == "A__FL" },
            // a run pattern: same line, direction and terminus stop (whatever its platform) → same next stops
            pattern = listOf(service.txt("LineRef"), service.txt("DirectionRef"), StopIds.fromOjp(service.txt("DestinationStopPointRef")).orEmpty())
                .joinToString("|"),
        )
    }

    private class ContextPlace(val name: String, val position: GeoPoint?)

    /** Places of the response context: stop points and stop places by reference. */
    private fun contextPlaces(doc: Document): Map<String, ContextPlace> {
        val map = HashMap<String, ContextPlace>()
        for (p in doc.all("Place")) {
            val sp = p.el("StopPoint")
            val spl = p.el("StopPlace")
            val ref = when {
                sp != null -> sp.txt("StopPointRef")
                spl != null -> spl.txt("StopPlaceRef")
                else -> ""
            }
            if (ref.isEmpty()) continue
            map[ref] = ContextPlace(if (sp != null) sp.txt("StopPointName") else spl.txt("StopPlaceName"), geo(p))
        }
        return map
    }

    /** A stop of a call, named by the call or else by the context, positioned by the context (platform, else stop place). */
    private fun station(ref: String, name: String, places: Map<String, ContextPlace>): Stop {
        val p = places[ref] ?: places[StopIds.stopPlaceOf(ref)]
        return Stop(StopIds.fromOjp(ref) ?: ref, name.ifEmpty { p?.name.orEmpty() }, p?.position)
    }

    private fun geo(node: Element?): GeoPoint? {
        val g = node.el("GeoPosition") ?: return null
        val lat = g.txt("Latitude").toDoubleOrNull() ?: return null
        val lon = g.txt("Longitude").toDoubleOrNull() ?: return null
        return GeoPoint(lat, lon)
    }

    private fun time(call: Element, kind: String, which: String): Instant? = SwissTime.parse(call.el(kind).txt(which))

    private fun eventTime(call: Element, kind: String): EventTime? =
        time(call, kind, "TimetabledTime")?.let { EventTime(it, time(call, kind, "EstimatedTime")) }

    private fun duration(text: String): Duration? =
        if (text.isEmpty()) null else try { Duration.parse(text) } catch (_: DateTimeParseException) { null }

    /** Traffic messages (SIRI SX situations) by number: the general perspective's text, in [lang] when given in it. */
    private fun situations(doc: Document, lang: String): Map<String, TrafficMessage> {
        val map = LinkedHashMap<String, TrafficMessage>()
        val want = lang.lowercase()
        for (s in doc.all("PtSituation")) {
            val id = s.txt("SituationNumber")
            if (id.isEmpty() || id in map) continue
            val actions = s.all("PassengerInformationAction")
            val pick = actions.firstOrNull { it.txt("Perspective") == "general" } ?: actions.firstOrNull()
            val content = pick.el("TextualContent")
            fun text(name: String): String {
                val nodes = content?.all(name).orEmpty()
                val n = nodes.firstOrNull { it.lang().lowercase() == want } ?: nodes.firstOrNull()
                return n?.textContent?.trim().orEmpty()
            }
            map[id] = TrafficMessage(
                id = id,
                severity = s.txt("Severity").ifEmpty { "normal" },
                planned = s.txt("Planned") == "true",
                periods = s.kids("ValidityPeriod").map { Period(SwissTime.parse(it.txt("StartTime")), SwissTime.parse(it.txt("EndTime"))) },
                summary = text("SummaryText"),
                description = text("DescriptionText"),
                consequence = text("ConsequenceText"),
                recommendation = text("RecommendationText"),
                duration = text("DurationText"),
            )
        }
        return map
    }

    /** The messages a service (or a leg) refers to. */
    private fun situationsOf(nodes: List<Element>, sits: Map<String, TrafficMessage>): List<TrafficMessage> =
        nodes.flatMap { it.el("SituationFullRefs").kids("SituationFullRef") }
            .map { it.txt("SituationNumber") }
            .distinct()
            .mapNotNull { sits[it] }

    /** "No results" and similar conditions: HTTP 200 with an `ErrorCondition`. */
    private fun notice(doc: Document): String? {
        val e = doc.all("ErrorCondition").firstOrNull() ?: return null
        return e.txt("Description").ifEmpty { e.textContent.trim() }.take(NOTICE_MAX)
    }
}

/** A next stop of a run pattern, reached [offset] after the departure from the board's stop. */
data class PatternStop(val id: String, val name: String, val offset: Duration?, val position: GeoPoint?, val platform: String?)

/**
 * Next stops of each run pattern, remembered from full boards so light refreshes can rebuild them (US-50).
 * The caller keeps one per stop for as long as it likes (the relay: a day).
 */
class RunPatterns {
    private val map = HashMap<String, List<PatternStop>>()
    operator fun get(pattern: String): List<PatternStop>? = map[pattern]
    operator fun set(pattern: String, stops: List<PatternStop>) {
        map[pattern] = stops
    }
    val size: Int get() = map.size
}
