package io.github.tiagsant.spt.core.ojp

import io.github.tiagsant.spt.core.model.Board
import io.github.tiagsant.spt.core.model.PlaceType
import io.github.tiagsant.spt.core.model.Zone
import java.io.IOException
import java.io.InterruptedIOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URI
import java.time.Clock
import java.time.Duration
import java.time.Instant

/** An HTTP answer: status, body and the `Retry-After` header when there is one. */
data class OjpHttpResponse(val status: Int, val body: String, val retryAfter: String? = null)

/** Sends an OJP request body and returns the raw answer. Throws [IOException] when the network fails. */
fun interface OjpTransport {
    fun post(body: String): OjpHttpResponse
}

/**
 * Transport over `HttpURLConnection` (available on the JVM and on Android, no dependency).
 * The [token] is the opentransportdata.swiss key: only the relay holds one (ADR-0002).
 */
class HttpOjpTransport(
    private val token: String,
    private val endpoint: String = OjpRequests.ENDPOINT,
    private val connectTimeout: Duration = Duration.ofSeconds(10),
    private val readTimeout: Duration = Duration.ofSeconds(20),
) : OjpTransport {
    override fun post(body: String): OjpHttpResponse {
        val conn = URI(endpoint).toURL().openConnection() as HttpURLConnection
        try {
            conn.requestMethod = "POST"
            conn.connectTimeout = connectTimeout.toMillis().toInt()
            conn.readTimeout = readTimeout.toMillis().toInt()
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/xml; charset=utf-8")
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val status = conn.responseCode
            val stream = if (status in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.use { it.readBytes().toString(Charsets.UTF_8) }.orEmpty()
            return OjpHttpResponse(status, text, conn.getHeaderField("Retry-After"))
        } finally {
            conn.disconnect()
        }
    }
}

/**
 * OJP 2.0 client: builds the request, sends it, reads the answer into the domain model.
 * Calls block; run them off the main thread. Failures are [OjpException]s.
 */
class OjpClient(
    private val transport: OjpTransport,
    private val requests: OjpRequests = OjpRequests(),
    private val clock: Clock = Clock.systemUTC(),
) {
    fun stopsByName(name: String, lang: String, limit: Int = 20, zone: Zone? = null): StopSearchResult =
        OjpParser.stops(send(requests.locationsByName(name, lang, now(), limit, listOf(PlaceType.STOP), zone)))

    fun placesByName(name: String, lang: String, limit: Int = 30, zone: Zone? = null): PlaceSearchResult =
        OjpParser.places(send(requests.locationsByName(name, lang, now(), limit, PlaceType.entries, zone)))

    fun stopsInZone(zone: Zone, lang: String, limit: Int = 20): StopSearchResult =
        OjpParser.stops(send(requests.locationsInZone(zone, lang, now(), limit)))

    fun departures(
        stopId: String,
        lang: String,
        from: Instant = now(),
        limit: Int = 40,
        onward: Boolean = true,
        patterns: RunPatterns? = null,
    ): Board = OjpParser.board(send(requests.stopEvents(stopId, from, lang, now(), limit, onward)), stopId, patterns, lang)

    fun journeys(fromId: String, toId: String, lang: String, at: Instant = now(), arrive: Boolean = false, limit: Int = 4): TripResult =
        OjpParser.trips(send(requests.trip(fromId, toId, at, lang, now(), arrive, limit)), lang)

    private fun now(): Instant = clock.instant()

    private fun send(xml: String): String {
        val r = try {
            transport.post(xml)
        } catch (e: SocketTimeoutException) {
            throw OjpException.Timeout(e)
        } catch (e: InterruptedIOException) {
            throw OjpException.Timeout(e)
        } catch (e: IOException) {
            throw OjpException.Network(e)
        }
        return when (r.status) {
            in 200..299 -> {
                if (!r.body.trimStart().startsWith("<")) throw OjpException.Malformed("not an XML answer")
                r.body
            }
            401, 403 -> throw OjpException.Unauthorized(r.status)
            429 -> throw OjpException.RateLimited(retryAfter(r.retryAfter))
            else -> throw OjpException.Http(r.status, r.body.take(500))
        }
    }

    private fun retryAfter(header: String?): Duration? = header?.trim()?.toLongOrNull()?.takeIf { it >= 0 }?.let(Duration::ofSeconds)
}
