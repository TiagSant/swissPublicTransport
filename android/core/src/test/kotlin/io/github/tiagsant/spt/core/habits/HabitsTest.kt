package io.github.tiagsant.spt.core.habits

import java.time.Duration
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The prototype's habit rules (US-06, `prototype/index.html` "Habits"): half-life 30 days, usual from 1.5, 10-minute debounce. */
class HabitsTest {
    private val t0 = Instant.parse("2026-11-02T07:30:00Z")
    private fun days(n: Double) = Duration.ofMillis((n * 86_400_000).toLong())
    private val key = "tram|14>8587082"

    @Test
    fun aUseCountsOneAndHalvesEvery30Days() {
        val u = Habits.record(null, t0)!!
        assertEquals(1.0, Habits.score(u, t0))
        assertEquals(0.5, Habits.score(u, t0 + days(30.0)), 1e-12)
        assertEquals(0.25, Habits.score(u, t0 + days(60.0)), 1e-12)
        assertEquals(0.0, Habits.score(null, t0))
    }

    @Test
    fun oneUseIsNotAHabit() {
        val h = HabitScores()
        assertTrue(h.record(key, t0))
        assertFalse(h.isUsual(key, t0))
    }

    @Test
    fun twoUsesTheSameDayMakeAUsualDirection() {
        val h = HabitScores()
        h.record(key, t0)
        assertTrue(h.record(key, t0 + Duration.ofHours(9)))     // the ride back in the evening
        assertTrue(h.isUsual(key, t0 + Duration.ofHours(9)))
        // two uses always score slightly less than 2 with the decay: why the threshold is 1.5
        assertTrue(h.score(key, t0 + Duration.ofHours(9)) < 2.0)
    }

    @Test
    fun twoUsesUpTo30DaysApartMakeAUsualDirection() {
        val h = HabitScores()
        h.record(key, t0)
        h.record(key, t0 + days(30.0))
        assertEquals(1.5, h.score(key, t0 + days(30.0)), 1e-12)
        assertTrue(h.isUsual(key, t0 + days(30.0)))

        val late = HabitScores()
        late.record(key, t0)
        late.record(key, t0 + days(31.0))
        assertFalse(late.isUsual(key, t0 + days(31.0)))
    }

    @Test
    fun aUsualDirectionFadesWithoutUse() {
        val h = HabitScores()
        h.record(key, t0)
        h.record(key, t0 + Duration.ofHours(1))
        assertTrue(h.isUsual(key, t0 + days(10.0)))
        assertFalse(h.isUsual(key, t0 + days(20.0)))   // ≈ 2 × 0.5^(20/30) = 1.26
    }

    @Test
    fun tapsWithin10MinutesCountOnce() {
        val u = Habits.record(null, t0)!!
        assertNull(Habits.record(u, t0 + Duration.ofMinutes(9)))
        val h = HabitScores()
        h.record(key, t0)
        assertFalse(h.record(key, t0 + Duration.ofMinutes(5)))
        assertFalse(h.record(key, t0 + Duration.ofMinutes(9).plusSeconds(59)))
        assertFalse(h.isUsual(key, t0 + Duration.ofMinutes(10)))
        assertTrue(h.record(key, t0 + Duration.ofMinutes(10)))   // 10 minutes after the last counted use
        assertTrue(h.isUsual(key, t0 + Duration.ofMinutes(10)))
    }

    @Test
    fun usualAmongSeveralKeysAndSnapshot() {
        val h = HabitScores()
        val other = "bus|21>8592995"
        h.record(key, t0)
        h.record(key, t0 + Duration.ofHours(2))
        h.record(other, t0)
        assertEquals(setOf(key), h.usual(listOf(key, other, "never"), t0 + Duration.ofHours(2)))
        val restored = HabitScores(h.snapshot())
        assertEquals(h.score(key, t0 + days(3.0)), restored.score(key, t0 + days(3.0)))
    }
}
