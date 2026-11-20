package io.github.tiagsant.spt.core.model

/** Somewhere a journey can start or end: a stop, an address, a place of interest or a point on the map. */
sealed interface Place {
    val name: String
    val position: GeoPoint?

    data class StopPlace(val stop: Stop) : Place {
        override val name get() = stop.name
        override val position get() = stop.position
    }

    data class Address(
        override val name: String,
        override val position: GeoPoint,
        val street: String = "",
        val houseNumber: String = "",
        val town: String = "",
    ) : Place

    data class PointOfInterest(override val name: String, override val position: GeoPoint) : Place

    /** A bare position (a point picked on the map, the rider's position). */
    data class Point(override val name: String, override val position: GeoPoint?) : Place
}

/** Kinds of places a location search can return. */
enum class PlaceType(val ojp: String) { STOP("stop"), ADDRESS("address"), POI("poi") }
