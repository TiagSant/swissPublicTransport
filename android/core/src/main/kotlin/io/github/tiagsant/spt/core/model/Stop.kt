package io.github.tiagsant.spt.core.model

/**
 * A stop (a stop place, with its platforms when known).
 *
 * [id] is the app's 7-digit id ("8587387"), the one riders' saved stops use; see [StopIds].
 * [mode] is the main mode served, when the data gives one (search results).
 */
data class Stop(
    val id: String,
    val name: String,
    val position: GeoPoint? = null,
    val platforms: List<String> = emptyList(),
    val mode: Mode? = null,
)

/**
 * Stop identifiers. OJP uses Swiss location ids (SLOID): `ch:1:sloid:87387`, or for a platform
 * `ch:1:sloid:87387:0:128561`. The app uses 7-digit UIC-style ids: 85 + the number on 5 digits → `8587387`.
 * Same rules as `stopId7` in `assets/ojp.js`.
 */
object StopIds {
    private val SLOID = Regex("""^ch:1:sloid:(\d+)""")
    private val APP_ID = Regex("""^\d{7}$""")
    private const val PREFIX = "ch:1:sloid:"

    /** App id of an OJP reference (stop place or platform), or of an app id; `null` when it is neither. */
    fun fromOjp(ref: String?): String? {
        val s = ref.orEmpty()
        SLOID.find(s)?.let { m ->
            val n = m.groupValues[1]
            return if (n.length <= 5) "85" + n.padStart(5, '0') else n
        }
        return if (APP_ID.matches(s)) s else null
    }

    /** OJP stop place reference of an app id: `8587387` → `ch:1:sloid:87387`. */
    fun toSloid(appId: String): String = PREFIX + appId.removePrefix("85").trimStart('0')

    /** The stop place of a platform reference: `ch:1:sloid:87387:0:128561` → `ch:1:sloid:87387`. */
    fun stopPlaceOf(ref: String): String = SLOID.find(ref)?.value ?: ref
}
