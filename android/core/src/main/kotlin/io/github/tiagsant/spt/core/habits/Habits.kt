package io.github.tiagsant.spt.core.habits

import java.time.Duration
import java.time.Instant
import kotlin.math.pow

/** How much something was used: a [score] that fades with time, as of its [lastUse]. */
data class Usage(val score: Double, val lastUse: Instant)

/**
 * The habit model of the prototype (US-06): each use adds 1 to a score that halves every 30 days.
 *
 * - "usual" from a score of 1.5: two uses less than 30 days apart (1 + 0.5^(Δ / 30 d) ≥ 1.5). Not 2: with the
 *   decay, two uses always score slightly less than 2;
 * - several uses within 10 minutes count once (taps while choosing are not habits).
 */
object Habits {
    const val HALF_LIFE_DAYS = 30
    const val USUAL_MIN = 1.5
    val DEBOUNCE: Duration = Duration.ofMinutes(10)

    private const val HALF_LIFE_MS = HALF_LIFE_DAYS * 86_400_000.0

    /** Score of [usage] at [now]. */
    fun score(usage: Usage?, now: Instant): Double =
        if (usage == null) 0.0 else usage.score * 0.5.pow((now.toEpochMilli() - usage.lastUse.toEpochMilli()) / HALF_LIFE_MS)

    /** The usage after one more use at [now]; `null` when it counts as the same use as the last one (debounce). */
    fun record(usage: Usage?, now: Instant): Usage? =
        if (usage != null && Duration.between(usage.lastUse, now) < DEBOUNCE) null
        else Usage(score(usage, now) + 1, now)

    fun isUsual(usage: Usage?, now: Instant): Boolean = score(usage, now) >= USUAL_MIN
}

/**
 * Usages by key: the directions of a stop (`Departure.directionKey`), the rider's places… Not thread-safe; the
 * caller stores [snapshot] (TECH-14).
 */
class HabitScores(initial: Map<String, Usage> = emptyMap()) {
    private val usages = initial.toMutableMap()

    /** Records a use of [key]; `false` when it was debounced. */
    fun record(key: String, now: Instant): Boolean {
        val next = Habits.record(usages[key], now) ?: return false
        usages[key] = next
        return true
    }

    fun score(key: String, now: Instant): Double = Habits.score(usages[key], now)

    fun isUsual(key: String, now: Instant): Boolean = Habits.isUsual(usages[key], now)

    /** The keys among [keys] that are usual at [now]. */
    fun usual(keys: Iterable<String>, now: Instant): Set<String> = keys.filterTo(LinkedHashSet()) { isUsual(it, now) }

    fun snapshot(): Map<String, Usage> = usages.toMap()
}
