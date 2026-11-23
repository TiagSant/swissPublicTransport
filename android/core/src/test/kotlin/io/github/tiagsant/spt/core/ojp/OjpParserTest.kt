package io.github.tiagsant.spt.core.ojp

import io.github.tiagsant.spt.core.Fixtures
import io.github.tiagsant.spt.core.model.Mode
import io.github.tiagsant.spt.core.model.Place
import io.github.tiagsant.spt.core.model.SwissTime
import io.github.tiagsant.spt.core.model.Walk
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Behaviour of the reader beyond the parity check. The OJP probe refreshes `tests/fixtures/ojp` with live data, so
 * checks on those answers are structural; precise rules are checked on small answers written here.
 */
class OjpParserTest {
    // ---------- Small hand-written answers ----------
    private fun ojp(delivery: String) =
        """<?xml version="1.0" encoding="utf-8"?><OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">""" +
            "<OJPResponse><siri:ServiceDelivery>$delivery</siri:ServiceDelivery></OJPResponse></OJP>"

    private fun service(extra: String = "") =
        "<Service><OperatingDayRef>2026-11-16</OperatingDayRef><JourneyRef>j1</JourneyRef><LineRef>ojp:91014:A</LineRef>" +
            "<DirectionRef>H</DirectionRef><Mode><PtMode>tram</PtMode></Mode><PublishedServiceName><Text xml:lang=\"fr\">14</Text></PublishedServiceName>" +
            "<siri:OperatorRef>ojp:881</siri:OperatorRef><DestinationStopPointRef>ch:1:sloid:2083:0:1</DestinationStopPointRef>" +
            "<DestinationText><Text xml:lang=\"fr\">Meyrin-Gravière</Text></DestinationText>$extra</Service>"

    private val situation = "<Situations><PtSituation><siri:SituationNumber>sit-1</siri:SituationNumber>" +
        "<siri:ValidityPeriod><siri:StartTime>2026-11-16T05:00:00Z</siri:StartTime><siri:EndTime>2026-11-16T08:00:00Z</siri:EndTime></siri:ValidityPeriod>" +
        "<siri:Severity>slight</siri:Severity><siri:Planned>true</siri:Planned><siri:PublishingActions><siri:PublishingAction>" +
        "<siri:PassengerInformationAction><siri:Perspective>stopPoint</siri:Perspective><siri:TextualContent>" +
        "<siri:SummaryContent><siri:SummaryText xml:lang=\"fr\">Arrêt déplacé</siri:SummaryText></siri:SummaryContent></siri:TextualContent></siri:PassengerInformationAction>" +
        "<siri:PassengerInformationAction><siri:Perspective>general</siri:Perspective><siri:TextualContent>" +
        "<siri:SummaryContent><siri:SummaryText xml:lang=\"de\">Bauarbeiten</siri:SummaryText><siri:SummaryText xml:lang=\"fr\">Travaux</siri:SummaryText></siri:SummaryContent>" +
        "<siri:DescriptionContent><siri:DescriptionText xml:lang=\"de\">Umleitung</siri:DescriptionText></siri:DescriptionContent>" +
        "</siri:TextualContent></siri:PassengerInformationAction></siri:PublishingAction></siri:PublishingActions></PtSituation></Situations>"

    private fun call(kind: String, planned: String, estimated: String? = null) =
        "<$kind><TimetabledTime>$planned</TimetabledTime>${estimated?.let { "<EstimatedTime>$it</EstimatedTime>" }.orEmpty()}</$kind>"

    private val here = "<siri:StopPointRef>ch:1:sloid:87418:0:906408</siri:StopPointRef>"

    private val boardXml = ojp(
        "<OJPStopEventDelivery><StopEventResponseContext>$situation</StopEventResponseContext>" +
            "<StopEventResult><StopEvent><ThisCall><CallAtStop>$here" +
            "<StopPointName><Text xml:lang=\"fr\">Confignon, croisée</Text></StopPointName>" +
            "<PlannedQuay><Text xml:lang=\"fr\">A</Text></PlannedQuay><EstimatedQuay><Text xml:lang=\"fr\">B</Text></EstimatedQuay>" +
            call("ServiceDeparture", "2026-11-16T06:24:00Z", "2026-11-16T06:25:12Z") + "</CallAtStop></ThisCall>" +
            service("<SituationFullRefs><SituationFullRef><siri:ParticipantRef>x</siri:ParticipantRef><siri:SituationNumber>sit-1</siri:SituationNumber></SituationFullRef></SituationFullRefs>") +
            "</StopEvent></StopEventResult>" +
            // a cancelled run and a stop not served: left out of the board
            "<StopEventResult><StopEvent><ThisCall><CallAtStop>$here" + call("ServiceDeparture", "2026-11-16T06:30:00Z") + "</CallAtStop></ThisCall>" +
            service("<Cancelled>true</Cancelled>") + "</StopEvent></StopEventResult>" +
            "<StopEventResult><StopEvent><ThisCall><CallAtStop>$here<NotServicedStop>true</NotServicedStop>" + call("ServiceDeparture", "2026-11-16T06:31:00Z") +
            "</CallAtStop></ThisCall>" + service() + "</StopEvent></StopEventResult></OJPStopEventDelivery>",
    )

    @Test
    fun aDepartureInSwissTimeWithItsDelayPlatformAndMessage() {
        val board = OjpParser.board(boardXml, "8587386", lang = "fr")
        val dep = board.departures.single()
        assertEquals("07:24", SwissTime.hhmm(dep.time.scheduled))        // 06:24 UTC in November
        assertEquals("07:25", SwissTime.hhmm(dep.time.time))
        assertEquals(1, dep.time.delayMinutes)                            // 72 s late
        assertEquals("B", dep.platform.shown)
        assertTrue(dep.platform.changed)
        assertEquals(Mode.TRAM, dep.line.mode)
        assertEquals("14", dep.line.label)
        assertEquals("TPG", dep.line.operator?.name)
        assertEquals("Meyrin-Gravière", dep.destination)
        assertEquals("tram|14>to:Meyrin-Gravière", dep.directionKey)     // next stops unknown: the terminus
        assertEquals("Confignon, croisée", board.stop.name)
    }

    @Test
    fun trafficMessagesInTheAppsLanguageFromTheGeneralPerspective() {
        val fr = OjpParser.board(boardXml, "8587386", lang = "fr").departures.single().messages.single()
        assertEquals("Travaux", fr.summary)              // the general perspective, in French
        assertEquals("Umleitung", fr.description)        // no French text: the first one
        assertEquals("slight", fr.severity)
        assertTrue(fr.planned)
        assertTrue(fr.isValidAt(Instant.parse("2026-11-16T06:24:00Z")))
        assertFalse(fr.isValidAt(Instant.parse("2026-11-16T09:00:00Z")))
        assertEquals("Bauarbeiten", OjpParser.board(boardXml, "8587386", lang = "de").departures.single().messages.single().summary)
    }

    @Test
    fun aCancelledRideStaysInTheJourneyMarkedCancelled() {
        fun leg(cancelled: String) = "<Leg><TimedLeg><LegBoard>$here" +
            "<StopPointName><Text xml:lang=\"fr\">Confignon, croisée</Text></StopPointName>${call("ServiceDeparture", "2026-11-16T07:16:00Z")}</LegBoard>" +
            "<LegAlight><siri:StopPointRef>ch:1:sloid:87057:0:1</siri:StopPointRef><StopPointName><Text xml:lang=\"fr\">Genève, gare Cornavin</Text></StopPointName>" +
            "${call("ServiceArrival", "2026-11-16T07:34:00Z")}$cancelled</LegAlight>${service()}</TimedLeg></Leg>"
        val xml = ojp(
            "<OJPTripDelivery><TripResult><Trip><Duration>PT18M</Duration><Transfers>0</Transfers>${leg("")}</Trip></TripResult>" +
                "<TripResult><Trip><Duration>PT18M</Duration><Transfers>0</Transfers>${leg("<NotServicedStop>true</NotServicedStop>")}</Trip></TripResult></OJPTripDelivery>",
        )
        val (ok, cancelled) = OjpParser.trips(xml).journeys
        assertFalse(ok.cancelled)
        assertTrue(cancelled.cancelled)
        assertEquals("8587057", cancelled.rides.single().alight.stop.id)
        assertEquals("08:16", SwissTime.hhmm(ok.departure!!))
        assertEquals(18, ok.duration!!.toMinutes())
    }

    @Test
    fun noResultsIsANoticeNotAnError() {
        val xml = ojp(
            "<OJPLocationInformationDelivery><siri:ErrorCondition><siri:OtherError/>" +
                "<siri:Description>LOCATION_NORESULTS</siri:Description></siri:ErrorCondition></OJPLocationInformationDelivery>",
        )
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

    // ---------- Recorded answers (structure) ----------

    @Test
    fun stopsByName() {
        val r = OjpParser.stops(Fixtures.text("ojp/lir_name_belair.xml"))
        val belAir = r.stops.first { "Bel-Air" in it.name }
        assertTrue(Regex("""\d{7}""").matches(belAir.id))
        assertNotNull(belAir.position)
    }

    @Test
    fun addressesAndPlacesOfInterest() {
        val rhone = OjpParser.places(Fixtures.text("ojp-places/app_lir_address_rhone.xml")).places
        assertTrue(rhone.any { it is Place.Address && it.street.isNotEmpty() })
        val palexpo = OjpParser.places(Fixtures.text("ojp-places/app_lir_poi_palexpo.xml")).places
        assertTrue(palexpo.any { it is Place.PointOfInterest || it is Place.StopPlace })
        // building entrances ("60.1") are dropped when the main number is in the answer
        val entrances = OjpParser.places(Fixtures.text("ojp-places/app_lir_address_entrances.xml")).places.filterIsInstance<Place.Address>()
        assertTrue(entrances.none { '.' in it.houseNumber && entrances.any { m -> m.houseNumber == it.houseNumber.substringBefore('.') } })
    }

    @Test
    fun fullBoardThenLightRefreshKeepsTheNextStops() {
        val patterns = RunPatterns()
        val full = OjpParser.board(Fixtures.text("ojp/app_ser_croisee_full.xml"), "8587386", patterns, "fr")
        assertTrue(full.departures.isNotEmpty())
        assertTrue(full.departures.count { it.nextStops.isNotEmpty() } >= full.departures.size * 9 / 10)
        assertTrue(patterns.size > 0)

        val light = OjpParser.board(Fixtures.text("ojp/app_ser_croisee_light.xml"), "8587386", patterns, "fr")
        val rebuilt = light.departures.filter { it.nextStops.isNotEmpty() }
        assertTrue(rebuilt.size >= light.departures.size / 2, "next stops rebuilt for ${rebuilt.size} of ${light.departures.size}")
        for (d in rebuilt) {
            assertTrue(d.nextStops.size <= 8)
            assertEquals(d.line.key + ">" + d.nextStops.first().stop.id, d.directionKey)
            assertTrue(d.nextStops.all { s -> s.arrival.let { it == null || it >= d.time.time } })
        }
        // without known patterns a light refresh cannot tell the next stops
        val alone = OjpParser.board(Fixtures.text("ojp/app_ser_croisee_light.xml"), "8587386", RunPatterns(), "fr")
        assertEquals(alone.departures.size, alone.unknownPatterns)
    }

    @Test
    fun journeysWithRidesAndWalks() {
        val r = OjpParser.trips(Fixtures.text("ojp/app_tr_depart.xml"), "fr")
        assertTrue(r.journeys.isNotEmpty())
        for (j in r.journeys) {
            assertEquals("8587386", j.rides.first().board.stop.id)            // from Confignon, croisée
            assertNotNull(j.rides.first().departure)
            assertTrue(j.rides.zipWithNext().all { (a, b) -> a.arrival!!.scheduled <= b.departure!!.scheduled })
        }
        val first = OjpParser.trips(Fixtures.text("ojp/tr_coords.xml"), "fr").journeys.first().legs.first()
        assertTrue(first is Walk && first.from is Place.Point, "a journey from a point starts on foot")
    }

    @Test
    fun trainsThatSplit() {
        val re = OjpParser.trips(Fixtures.text("ojp-split/trip_zurich_konstanz.xml"), "fr").journeys.first().rides.first()
        assertTrue(re.multiDestination)
        assertEquals("RE", re.line.category)
        assertEquals(Mode.TRAIN, re.line.mode)
    }
}
