package io.github.tiagsant.spt.core.ojp

import io.github.tiagsant.spt.core.Fixtures
import io.github.tiagsant.spt.core.model.Mode
import io.github.tiagsant.spt.core.model.Place
import io.github.tiagsant.spt.core.model.Ride
import io.github.tiagsant.spt.core.model.SwissTime
import io.github.tiagsant.spt.core.model.Walk
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Behaviour of the reader on recorded answers, beyond the parity check. */
class OjpParserTest {
    @Test
    fun stopsByName() {
        val r = OjpParser.stops(Fixtures.text("ojp/lir_name_belair.xml"))
        assertNull(r.notice)
        val belAir = r.stops.first { it.id == "8587387" }
        assertEquals("Genève, Bel-Air", belAir.name)
        assertNotNull(belAir.position)
    }

    @Test
    fun addressesAndPlacesOfInterest() {
        val rhone = OjpParser.places(Fixtures.text("ojp-places/app_lir_address_rhone.xml")).places
        assertTrue(rhone.any { it is Place.Address && it.street.isNotEmpty() })
        val palexpo = OjpParser.places(Fixtures.text("ojp-places/app_lir_poi_palexpo.xml")).places
        assertTrue(palexpo.any { it is Place.PointOfInterest || it is Place.StopPlace })
        // building entrances ("60.1") are dropped when the main number is in the answer
        val lancy = OjpParser.places(Fixtures.text("ojp-places/app_lir_address_lancy.xml")).places.filterIsInstance<Place.Address>()
        assertTrue(lancy.none { '.' in it.houseNumber && lancy.any { m -> m.houseNumber == it.houseNumber.substringBefore('.') } })
    }

    @Test
    fun fullBoardThenLightRefreshKeepsTheNextStops() {
        val patterns = RunPatterns()
        val full = OjpParser.board(Fixtures.text("ojp/app_ser_esserts_full.xml"), "8587418", patterns, "fr")
        assertEquals("Petit-Lancy, Les Esserts", full.stop.name)
        // every run but those ending here has next stops
        assertTrue(full.departures.count { it.nextStops.isNotEmpty() } >= full.departures.size - 10)
        assertTrue(patterns.size > 0)

        val light = OjpParser.board(Fixtures.text("ojp/app_ser_esserts_light.xml"), "8587418", patterns, "fr")
        val tram = light.departures.first { it.line.name == "14" }
        assertEquals(Mode.TRAM, tram.line.mode)
        assertEquals("TPG", tram.line.operator?.name)
        assertTrue(tram.nextStops.size in 1..8)
        assertEquals("tram|14>8587082", tram.directionKey)     // next stop: Petit-Lancy, place
        // a light refresh without known patterns cannot tell the next stops
        val alone = OjpParser.board(Fixtures.text("ojp/app_ser_esserts_light.xml"), "8587418", RunPatterns(), "fr")
        assertEquals(alone.departures.size, alone.unknownPatterns)
    }

    @Test
    fun liveTimesAndSwissTime() {
        val dep = OjpParser.board(Fixtures.text("ojp/app_ser_esserts_light.xml"), "8587418").departures.first()
        assertEquals("07:24", SwissTime.hhmm(dep.time.scheduled))   // 06:24 UTC in November
        assertTrue(dep.time.live)
        assertEquals(1, dep.time.delayMinutes)                       // 72 s late
        assertEquals("A", dep.platform.shown)
    }

    @Test
    fun trafficMessagesInTheAppsLanguage() {
        val board = OjpParser.board(Fixtures.text("ojp/ser_geneve_gare.xml"), "8501008", lang = "fr")
        val msg = board.departures.flatMap { it.messages }.first()
        assertTrue(msg.summary.isNotEmpty())
        assertTrue(msg.periods.isNotEmpty())
    }

    @Test
    fun journeysWithRidesWalksAndCancellations() {
        val r = OjpParser.trips(Fixtures.text("ojp/app_tr_depart.xml"), "fr")
        val first = r.journeys.first()
        val ride = first.legs.single() as Ride
        assertEquals("8587418", ride.board.stop.id)
        assertEquals("8587057", ride.alight.stop.id)
        assertEquals(7, ride.intermediate.size)
        assertEquals("A", ride.board.platform.shown)
        // a cancelled tram in the live data (US-61)
        assertTrue(OjpParser.trips(Fixtures.text("ojp/tr_stops.xml"), "fr").journeys.any { it.cancelled })

        val coords = OjpParser.trips(Fixtures.text("ojp/tr_coords.xml"), "fr")
        val walk = coords.journeys.first().legs.first() as Walk
        assertTrue(walk.from is Place.Point)
        assertEquals("Petit-Lancy, Les Esserts", walk.to.name)
    }

    @Test
    fun trainsThatSplit() {
        val r = OjpParser.trips(Fixtures.text("ojp-split/trip_zurich_konstanz.xml"), "fr")
        val re = r.journeys.first().rides.first()
        assertTrue(re.multiDestination)
        assertEquals("RE", re.line.category)
        assertEquals(Mode.TRAIN, re.line.mode)
    }

    @Test
    fun noResultsIsANoticeNotAnError() {
        val xml = """<?xml version="1.0" encoding="utf-8"?><OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">
            <OJPResponse><siri:ServiceDelivery><OJPLocationInformationDelivery><siri:ErrorCondition><siri:OtherError/>
            <siri:Description>LOCATION_NORESULTS</siri:Description></siri:ErrorCondition></OJPLocationInformationDelivery>
            </siri:ServiceDelivery></OJPResponse></OJP>"""
        val r = OjpParser.stops(xml)
        assertTrue(r.stops.isEmpty())
        assertEquals("LOCATION_NORESULTS", r.notice)
    }

    @Test
    fun unreadableAnswersAreMalformed() {
        assertFailsWith<OjpException.Malformed> { OjpParser.stops("<OJP><unclosed></OJP>") }
        assertFailsWith<OjpException.Malformed> { OjpParser.trips("not xml at all") }
        // no DOCTYPE, so no entity expansion from the network
        assertFailsWith<OjpException.Malformed> {
            OjpParser.stops("""<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><OJP>&e;</OJP>""")
        }
    }

    @Test
    fun trainNames() {
        assertEquals("IR" to "57", OjpParser.splitTrainName("IR57"))
        assertEquals("R" to "L4", OjpParser.splitTrainName("RL4"))
        assertEquals("RE" to "33", OjpParser.splitTrainName("RE 33"))
        assertEquals("TGV" to "", OjpParser.splitTrainName("TGV"))
    }
}
