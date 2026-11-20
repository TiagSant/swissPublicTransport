package io.github.tiagsant.spt.core.model

import kotlin.math.cos

/** A WGS84 position. */
data class GeoPoint(val lat: Double, val lon: Double)

/** A rectangle on the map, as OJP's `GeoRestriction/Rectangle`. */
data class Zone(val latMin: Double, val latMax: Double, val lonMin: Double, val lonMax: Double) {
    init {
        require(latMin <= latMax && lonMin <= lonMax) { "empty zone: $this" }
    }

    operator fun contains(p: GeoPoint) = p.lat in latMin..latMax && p.lon in lonMin..lonMax

    companion object {
        private const val METERS_PER_DEGREE_LAT = 111_320.0

        /** The square of `2 × radius` metres centred on [center] ("stops near me"). */
        fun around(center: GeoPoint, radiusMeters: Double): Zone {
            val dLat = radiusMeters / METERS_PER_DEGREE_LAT
            val dLon = radiusMeters / (METERS_PER_DEGREE_LAT * cos(Math.toRadians(center.lat)))
            return Zone(center.lat - dLat, center.lat + dLat, center.lon - dLon, center.lon + dLon)
        }
    }
}
