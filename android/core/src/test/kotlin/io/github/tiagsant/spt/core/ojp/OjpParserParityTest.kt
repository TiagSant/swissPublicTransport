package io.github.tiagsant.spt.core.ojp

import io.github.tiagsant.spt.core.Fixtures
import io.github.tiagsant.spt.core.model.Board
import io.github.tiagsant.spt.core.model.EventTime
import io.github.tiagsant.spt.core.model.GeoPoint
import io.github.tiagsant.spt.core.model.Place
import io.github.tiagsant.spt.core.model.Ride
import io.github.tiagsant.spt.core.model.Stop
import io.github.tiagsant.spt.core.model.SwissTime
import io.github.tiagsant.spt.core.model.TrafficMessage
import io.github.tiagsant.spt.core.model.Walk
import java.io.File
import java.time.Duration
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Every recorded answer is read with the same result as the prototype's `assets/ojp.js`.
 *
 * `scripts/ojp_kotlin_parity.mjs` wrote what the prototype reads from each answer, one line per item
 * (`tests/fixtures/ojp-kotlin/answers`); this test writes the same lines from the Kotlin model and compares them.
 */
class OjpParserParityTest {
    private val answers = Fixtures.file("ojp-kotlin/answers")

    // ---------- Same line format as the oracle ----------
    private fun clean(v: Any?): String = when {
        v == null || v == "" -> "-"
        else -> v.toString().replace("\\", "\\\\").replace("|", "\\|").replace(Regex("\r?\n"), "\\\\n")
    }
    private fun line(vararg xs: Any?) = xs.joinToString("|") { clean(it) }
    private fun time(t: Instant?) = t?.let(SwissTime::isoMillis)
    private fun coord(p: GeoPoint?) = p?.let { "${js(it.lat)},${js(it.lon)}" }
    private fun js(d: Double) = OjpRequests.num(d)
    private fun st(s: Stop) = "${s.id}~${s.name}"
    private fun place(p: Place) = if (p is Place.StopPlace) st(p.stop) else "~${p.name}"
    private fun sitIds(list: List<TrafficMessage>) = list.joinToString(",") { it.id }.ifEmpty { null }
    private fun sitLines(all: List<TrafficMessage>) = all.distinctBy { it.id }.sortedBy { it.id }.map { s ->
        line(
            "sit", s.id, s.severity, s.planned,
            s.periods.joinToString(",") { "${time(it.start).orEmpty()}/${time(it.end).orEmpty()}" },
            s.summary, s.description, s.consequence, s.recommendation, s.duration,
        )
    }
    // ISO duration → "hh:mm:ss" as the prototype's durationHMS
    private fun hms(d: Duration?) = d?.let { "%02d:%02d:%02d".format(it.toHours(), it.toMinutesPart(), Math.round(it.toSecondsPart() + it.toNanosPart() / 1e9)) }
    private fun planned(t: EventTime?) = time(t?.scheduled)
    private fun live(t: EventTime?) = time(t?.estimated)

    private fun stops(xml: String): List<String> {
        val r = OjpParser.stops(xml)
        return r.stops.map { line("stop", it.id, it.name, coord(it.position), it.mode?.key) } + line("error", r.notice)
    }

    private fun places(xml: String): List<String> {
        val r = OjpParser.places(xml)
        return r.places.map {
            when (it) {
                is Place.StopPlace -> line("stop", it.stop.id, it.name, coord(it.position), null, null, null)
                is Place.Address -> line("address", null, it.name, coord(it.position), it.street, it.houseNumber, it.town)
                is Place.PointOfInterest -> line("poi", null, it.name, coord(it.position), null, null, null)
                is Place.Point -> error("no bare points in a location answer")
            }
        } + line("error", r.notice)
    }

    private fun board(b: Board): List<String> {
        val out = mutableListOf(line("station", b.stop.id, b.stop.name, coord(b.stop.position)), line("unknownPatterns", b.unknownPatterns))
        for (d in b.departures) out += line(
            "dep", d.line.category, d.line.number, d.line.name, d.line.operator?.name, d.line.operator?.ref, d.destination, d.multiDestination,
            time(d.time.scheduled), time(d.time.estimated), d.platform.planned, d.platform.estimated,
            st(d.stop), sitIds(d.messages),
            d.nextStops.joinToString(";") { "${it.stop.id}~${it.stop.name}~${time(it.arrival).orEmpty()}~${it.platform.orEmpty()}~${coord(it.stop.position).orEmpty()}" },
        )
        out += sitLines(b.departures.flatMap { it.messages })
        out += line("error", b.notice)
        return out
    }

    private fun trips(xml: String): List<String> {
        val r = OjpParser.trips(xml, "fr")
        val out = mutableListOf<String>()
        val sits = mutableListOf<TrafficMessage>()
        for (j in r.journeys) {
            out += line("trip", j.duration?.let { Math.round(it.toMillis() / 1000.0) }, j.transfers)
            for (leg in j.legs) when (leg) {
                is Ride -> {
                    sits += leg.messages
                    out += line(
                        "ride", leg.line.category, leg.line.number, leg.line.name, leg.line.operator?.name, leg.line.operator?.ref,
                        leg.destination, leg.multiDestination, leg.cancelled,
                        st(leg.board.stop), planned(leg.board.departure), live(leg.board.departure), leg.board.platform.planned, leg.board.platform.estimated,
                        st(leg.alight.stop), planned(leg.alight.arrival), live(leg.alight.arrival), leg.alight.platform.planned, leg.alight.platform.estimated,
                        sitIds(leg.messages),
                        leg.calls.joinToString(";") {
                            "${it.stop.id}~${planned(it.arrival).orEmpty()}~${live(it.arrival).orEmpty()}~${planned(it.departure).orEmpty()}~${live(it.departure).orEmpty()}"
                        },
                    )
                }
                is Walk -> out += line("walk", hms(leg.duration), place(leg.from), place(leg.to))
                else -> error("unexpected leg $leg")
            }
        }
        out += sitLines(sits)
        out += line("error", r.notice)
        return out
    }

    private fun assertSameLines(expected: List<String>, actual: List<String>, name: String) {
        for (i in 0 until maxOf(expected.size, actual.size)) {
            val e = expected.getOrNull(i)
            val a = actual.getOrNull(i)
            if (e != a) fail("$name, line ${i + 1}:\n  prototype: $e\n  kotlin:    $a")
        }
    }

    @Test
    fun everyRecordedAnswerReadsAsInThePrototype() {
        val files = answers.listFiles { f -> f.name.endsWith(".txt") }!!.sortedBy { it.name }
        assertTrue(files.size >= 40, "oracle answers missing: ${files.size}")
        // per folder and stop, a light board reuses the run patterns of a full one (as the prototype's caller)
        val patterns = HashMap<String, RunPatterns>()
        val ordered = files.sortedWith(compareBy<File>({ "_light" in it.name }, { it.name }))
        for (f in ordered) {
            val expected = f.readLines()
            val (fixture, kind) = f.name.removeSuffix(".txt").let { it.substringBeforeLast('.') to it.substringAfterLast('.') }
            val (dir, name) = fixture.split("__", limit = 2)
            val xml = Fixtures.text("$dir/$name.xml")
            val actual = when (kind) {
                "locations" -> stops(xml)
                "places" -> places(xml)
                "trips" -> trips(xml)
                "board" -> {
                    val stopId = expected.first().substringAfter("stopId|")
                    val p = patterns.getOrPut("$dir/$stopId") { RunPatterns() }
                    listOf("stopId|$stopId") + board(OjpParser.board(xml, stopId, p, "fr"))
                }
                else -> error("unknown kind $kind")
            }
            assertSameLines(expected, actual, f.name)
        }
    }
}
