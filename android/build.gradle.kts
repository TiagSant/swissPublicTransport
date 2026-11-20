plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.compose) apply false
}

/*
 * ADR-0003: no Google service in the app. Any Play Services or Firebase dependency, direct or transitive, fails the
 * build as soon as a configuration is resolved. `-PnoGoogleSelfTest` adds one on purpose so CI can check the guard.
 */
val forbiddenGroups = listOf("com.google.android.gms", "com.google.firebase")

subprojects {
    configurations.configureEach {
        resolutionStrategy.eachDependency {
            if (forbiddenGroups.any { requested.group == it || requested.group.startsWith("$it.") }) {
                throw GradleException(
                    "${requested.group}:${requested.name} is a Google service dependency, refused by ADR-0003 " +
                        "(docs/architecture/decisions/0003-no-google-fdroid.md).",
                )
            }
        }
    }
}
