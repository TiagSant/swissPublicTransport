package io.github.tiagsant.spt.core.ojp

import io.github.tiagsant.spt.core.Fixtures
import java.io.IOException
import java.net.SocketTimeoutException
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.ZoneOffset
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/** The client sends the prototype's XML and turns HTTP and network failures into typed errors. */
class OjpClientTest {
    // the recorded request of the app's light board refresh, and its times (the OJP probe refreshes it)
    private val recorded = Fixtures.text("ojp/app_ser_esserts_light.request.xml")
    private fun tag(name: String) = Instant.parse(Regex("<$name>([^<]+)</$name>").find(recorded)!!.groupValues[1])
    private val clock = Clock.fixed(tag("siri:RequestTimestamp"), ZoneOffset.UTC)
    private fun client(t: OjpTransport) = OjpClient(t, OjpRequests("swissPublicTransport_prototype"), clock)
    private fun answering(status: Int, body: String = "", retryAfter: String? = null) = client { OjpHttpResponse(status, body, retryAfter) }

    @Test
    fun sendsTheRequestAndReadsTheAnswer() {
        var sent = ""
        val c = client { body -> sent = body; OjpHttpResponse(200, Fixtures.text("ojp/app_ser_esserts_light.xml")) }
        val board = c.departures("8587418", "fr", from = tag("DepArrTime"), limit = 150, onward = false)
        assertEquals(recorded, sent)
        assertTrue(board.departures.isNotEmpty())
    }

    @Test
    fun badKey() {
        assertEquals(401, assertFailsWith<OjpException.Unauthorized> { answering(401).stopsByName("Bel-Air", "fr") }.status)
        assertEquals(403, assertFailsWith<OjpException.Unauthorized> { answering(403).stopsByName("Bel-Air", "fr") }.status)
    }

    @Test
    fun requestLimit() {
        assertEquals(Duration.ofSeconds(30), assertFailsWith<OjpException.RateLimited> { answering(429, retryAfter = "30").stopsByName("x", "fr") }.retryAfter)
        assertEquals(null, assertFailsWith<OjpException.RateLimited> { answering(429).stopsByName("x", "fr") }.retryAfter)
    }

    @Test
    fun timeoutAndNetwork() {
        assertFailsWith<OjpException.Timeout> { client { throw SocketTimeoutException("read timed out") }.stopsByName("x", "fr") }
        assertFailsWith<OjpException.Network> { client { throw IOException("no route to host") }.stopsByName("x", "fr") }
    }

    @Test
    fun otherHttpErrorsAndMalformedAnswers() {
        assertEquals(503, assertFailsWith<OjpException.Http> { answering(503, "down").journeys("8587418", "8587057", "fr") }.status)
        assertFailsWith<OjpException.Malformed> { answering(200, "{\"json\": true}").journeys("8587418", "8587057", "fr") }
        assertFailsWith<OjpException.Malformed> { answering(200, "<OJP><broken").stopsByName("x", "fr") }
    }
}
