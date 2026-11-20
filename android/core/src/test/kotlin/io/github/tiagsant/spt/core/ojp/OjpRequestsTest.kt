package io.github.tiagsant.spt.core.ojp

import io.github.tiagsant.spt.core.Fixtures
import io.github.tiagsant.spt.core.model.PlaceType
import io.github.tiagsant.spt.core.model.Zone
import java.io.File
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The XML sent is the one `assets/ojp.js` builds. `scripts/ojp_kotlin_parity.mjs` wrote, for each case, the
 * parameters and the prototype's XML; the cases include every recorded request of the app.
 */
class OjpRequestsTest {
    private val requests = OjpRequests(requestor = "swissPublicTransport_prototype")

    private fun params(f: File): Map<String, String> =
        f.readLines().filter { '=' in it }.associate { it.substringBefore('=') to it.substringAfter('=') }

    private fun build(p: Map<String, String>): String {
        val lang = p.getValue("lang")
        val now = Instant.parse(p.getValue("now"))
        val zone = p["zone"]?.split(',')?.map(String::toDouble)?.let { (a, b, c, d) -> Zone(a, b, c, d) }
        val types = p["types"]?.split(',')?.map { t -> PlaceType.entries.first { it.ojp == t } } ?: listOf(PlaceType.STOP)
        return when (p.getValue("kind")) {
            "byName" -> requests.locationsByName(p.getValue("name"), lang, now, p.getValue("limit").toInt(), types, zone)
            "inZone" -> requests.locationsInZone(zone!!, lang, now, p.getValue("limit").toInt())
            "stopEvents" -> requests.stopEvents(
                p.getValue("stopId"), Instant.parse(p.getValue("from")), lang, now, p.getValue("limit").toInt(), p.getValue("onward").toBoolean(),
            )
            "trip" -> requests.trip(
                p.getValue("fromId"), p.getValue("toId"), Instant.parse(p.getValue("at")), lang, now,
                p.getValue("arrive").toBoolean(), p.getValue("limit").toInt(),
            )
            else -> error("unknown kind in $p")
        }
    }

    @Test
    fun sameXmlAsThePrototypeForEveryCase() {
        val cases = Fixtures.file("ojp-kotlin/requests").listFiles { f -> f.name.endsWith(".params") }!!.sortedBy { it.name }
        assertTrue(cases.size >= 18, "cases missing: ${cases.size}")
        assertTrue(cases.count { it.name.startsWith("recorded_") } >= 11, "recorded requests missing")
        for (c in cases) {
            val expected = File(c.path.removeSuffix(".params") + ".xml").readText()
            assertEquals(expected, build(params(c)), c.name)
        }
    }

    @Test
    fun recordedRequestsAreTheAppsOwn() {
        // the oracle rebuilt them from the recorded files; check one directly against the recording
        val recorded = Fixtures.text("ojp/app_ser_esserts_light.request.xml")
        fun tag(name: String) = Instant.parse(Regex("<$name>([^<]+)</$name>").find(recorded)!!.groupValues[1])
        val xml = requests.stopEvents("8587418", tag("DepArrTime"), "fr", tag("siri:RequestTimestamp"), 150, onward = false)
        assertEquals(recorded, xml)
    }

    @Test
    fun numbersAndEscaping() {
        assertEquals("46", OjpRequests.num(46.0))
        assertEquals("6.1066", OjpRequests.num(6.1066))
        assertEquals("0.0001", OjpRequests.num(0.0001))
        assertEquals("-0.5", OjpRequests.num(-0.5))
        assertEquals("a &lt;b&gt; &amp; &apos;c&apos; &quot;d&quot;", OjpRequests.esc("a <b> & 'c' \"d\""))
        assertTrue(OjpRequests().locationsByName("x", "fr", Instant.EPOCH).contains("<siri:RequestorRef>swissPublicTransport</siri:RequestorRef>"))
    }
}
