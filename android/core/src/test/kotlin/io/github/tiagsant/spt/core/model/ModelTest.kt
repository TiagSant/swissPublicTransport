package io.github.tiagsant.spt.core.model

import java.time.Duration
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class StopIdsTest {
    @Test
    fun ojpReferencesBecomeAppIds() {
        assertEquals("8587387", StopIds.fromOjp("ch:1:sloid:87387"))
        assertEquals("8587387", StopIds.fromOjp("ch:1:sloid:87387:0:128561"))   // a platform: its stop place
        assertEquals("8507000", StopIds.fromOjp("ch:1:sloid:7000"))             // padded to 5 digits
        assertEquals("8774100", StopIds.fromOjp("ch:1:sloid:8774100"))          // already a full id
        assertEquals("8501008", StopIds.fromOjp("8501008"))
        assertNull(StopIds.fromOjp("850100"))
        assertNull(StopIds.fromOjp("ch:2:sloid:1"))
        assertNull(StopIds.fromOjp(null))
    }

    @Test
    fun appIdsBecomeOjpReferences() {
        assertEquals("ch:1:sloid:87387", StopIds.toSloid("8587387"))
        assertEquals("ch:1:sloid:7000", StopIds.toSloid("8507000"))
        assertEquals("ch:1:sloid:87387", StopIds.stopPlaceOf("ch:1:sloid:87387:0:128561"))
        for (id in listOf("8587387", "8507000", "8501008", "8592995")) assertEquals(id, StopIds.fromOjp(StopIds.toSloid(id)))
    }
}

class LineTest {
    private fun label(category: String, number: String) = Line(category, number, number).label

    @Test
    fun modesFromCategories() {
        assertEquals(Mode.TRAM, Mode.ofCategory("T"))
        assertEquals(Mode.BUS, Mode.ofCategory(" nfb "))
        assertEquals(Mode.SHIP, Mode.ofCategory("BAT"))
        assertEquals(Mode.TRAIN, Mode.ofCategory("IR"))
        assertEquals(Mode.METRO, Mode.ofCategory("M"))
        assertEquals(Mode.CABLEWAY, Mode.ofCategory("GB"))
        assertEquals(Mode.OTHER, Mode.ofCategory("XYZ"))
        assertEquals(Mode.SHIP, Mode.ofOjp("water"))
        assertNull(Mode.ofOjp("spaceship"))
    }

    @Test
    fun badgeLabelsAsInThePrototype() {
        assertEquals("14", label("T", "14"))
        assertEquals("m2", label("M", "2"))          // Lausanne metro
        assertEquals("m1", label("M", "M1"))
        assertEquals("L1", label("R", "L1"))         // Léman Express
        assertEquals("IR 57", label("IR", "57"))
        assertEquals("RE 33", label("RE", "33"))
        assertEquals("IC", label("IC", "1068"))      // run number: the category only
        assertEquals("TGV", label("TGV", ""))
        assertEquals("?", label("", ""))
        assertEquals("tram|14", Line("T", "14", "14").key)
    }
}

class TimeTest {
    private val t0 = Instant.parse("2026-11-16T06:57:00Z")

    @Test
    fun liveTimeAndDelay() {
        val onTime = EventTime(t0)
        assertFalse(onTime.live)
        assertEquals(t0, onTime.time)
        assertEquals(0, onTime.delayMinutes)

        val late = EventTime(t0, t0.plusSeconds(48))     // 48 s late rounds to 1 min
        assertTrue(late.live)
        assertEquals(1, late.delayMinutes)
        assertEquals(0, EventTime(t0, t0.plusSeconds(29)).delayMinutes)
        assertEquals(1, EventTime(t0, t0.plusSeconds(30)).delayMinutes)   // Math.round: half up
        assertEquals(-2, EventTime(t0, t0.minusSeconds(100)).delayMinutes)
        assertEquals(t0.plusSeconds(180), EventTime.withDelay(t0, 3).time)
    }

    @Test
    fun swissLocalTimeInWinterAndSummer() {
        assertEquals("07:57", SwissTime.hhmm(t0))                                        // CET, UTC+1
        assertEquals("08:57", SwissTime.hhmm(Instant.parse("2026-07-16T06:57:00Z")))    // CEST, UTC+2
        assertEquals("2026-11-16 07:57", SwissTime.apiDateTime(t0))
        // the night clocks go back: 02:30 happens twice
        assertEquals("02:30", SwissTime.hhmm(Instant.parse("2026-10-25T00:30:00Z")))
        assertEquals("02:30", SwissTime.hhmm(Instant.parse("2026-10-25T01:30:00Z")))
    }

    @Test
    fun readsEveryTimeFormatOfTheData() {
        assertEquals(t0, SwissTime.parse("2026-11-16T06:57:00Z"))
        assertEquals(t0, SwissTime.parse("2026-11-16T07:57:00+01:00"))
        assertEquals(t0, SwissTime.parse("2026-11-16T07:57:00+0100"))
        assertEquals(Instant.parse("2026-11-16T06:55:40.4294405Z"), SwissTime.parse("2026-11-16T07:55:40.4294405+01:00"))
        assertNull(SwissTime.parse(""))
        assertNull(SwissTime.parse("soon"))
        assertEquals("2026-11-16T06:57:00.000Z", SwissTime.isoMillis(t0))
        assertEquals("2026-11-16T06:55:40.429Z", SwissTime.isoMillis(Instant.parse("2026-11-16T06:55:40.4294405Z")))
    }

    @Test
    fun platforms() {
        assertEquals("A", Platform("A").shown)
        assertEquals("B", Platform("A", "B").shown)
        assertTrue(Platform("A", "B").changed)
        assertFalse(Platform("A", "A").changed)
        assertNull(Platform.NONE.shown)
    }
}

class ZoneTest {
    @Test
    fun zoneAroundAPoint() {
        val croisee = GeoPoint(46.17890, 6.09018)
        val z = Zone.around(croisee, 500.0)
        assertTrue(croisee in z)
        assertEquals(0.00449, z.latMax - croisee.lat, 0.00001)
        assertTrue(z.lonMax - croisee.lon > z.latMax - croisee.lat)   // a degree of longitude is shorter
        assertFalse(GeoPoint(46.2, 6.09018) in z)
        assertFailsWith<IllegalArgumentException> { Zone(47.0, 46.0, 6.0, 7.0) }
    }
}

class TrafficMessageTest {
    @Test
    fun validOnlyWithinItsPeriods() {
        val t = Instant.parse("2026-11-16T12:00:00Z")
        val always = TrafficMessage("a")
        val weekend = TrafficMessage("b", periods = listOf(Period(Instant.parse("2026-11-14T23:00:00Z"), Instant.parse("2026-11-15T22:59:00Z"))))
        val fromNow = TrafficMessage("c", periods = listOf(Period(t, null)))
        assertTrue(always.isValidAt(t))
        assertFalse(weekend.isValidAt(t))
        assertTrue(fromNow.isValidAt(t))
        assertFalse(fromNow.isValidAt(t.minusSeconds(1)))
        assertEquals(listOf("a", "c"), listOf(always, weekend, fromNow).validAt(t).map { it.id })
    }
}

class JourneyTest {
    private val line = Line("T", "14", "14")
    private fun at(hhmm: String) = Instant.parse("2026-11-16T${hhmm}:00Z")
    private fun stop(id: String) = Stop(id, "Stop $id")
    private fun ride(from: String, dep: String, to: String, arr: String, depLive: String? = null) = Ride(
        line, "Terminus",
        listOf(Call(stop(from), departure = EventTime(at(dep), depLive?.let(::at))), Call(stop(to), arrival = EventTime(at(arr)))),
    )

    @Test
    fun waitsBetweenRidesOnceTheWalkIsDone() {
        val j = Journey(
            listOf(
                ride("8587386", "07:00", "8587387", "07:10"),
                Walk(Place.StopPlace(stop("8587387")), Place.StopPlace(stop("8587388")), Duration.ofMinutes(3)),
                ride("8587388", "07:20", "8587057", "07:30"),
            ),
            Duration.ofMinutes(30), 1,
        )
        val steps = j.withWaits()
        assertEquals(listOf("Ride", "Walk", "Wait", "Ride"), steps.map { it::class.simpleName })
        val wait = steps[2] as Wait
        assertEquals(at("07:13"), wait.from)
        assertEquals(Duration.ofMinutes(7), wait.duration)
        assertEquals("8587388", wait.at.id)
        assertEquals(Duration.ofMinutes(3), j.walking)
        assertEquals(at("07:00"), j.departure)
        assertEquals(at("07:30"), j.arrival)
    }

    @Test
    fun noWaitWhenTheNextRideIsLateEnoughOrLive() {
        val tight = Journey(listOf(ride("1", "07:00", "2", "07:10"), ride("2", "07:10", "3", "07:20")))
        assertEquals(2, tight.withWaits().size)
        val live = Journey(listOf(ride("1", "07:00", "2", "07:10"), ride("2", "07:08", "3", "07:20", depLive = "07:12")))
        assertEquals(Duration.ofMinutes(2), (live.withWaits()[1] as Wait).duration)
    }

    @Test
    fun aRideHasABoardingAndAGettingOffStop() {
        assertFailsWith<IllegalArgumentException> { Ride(line, "x", listOf(Call(stop("1")))) }
    }
}
