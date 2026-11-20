import org.jetbrains.kotlin.gradle.dsl.JvmTarget

// Shared core (TECH-11, TECH-12): pure Kotlin on the JVM, used by the app and the relay. No dependency.
plugins {
    alias(libs.plugins.kotlin.jvm)
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
        allWarningsAsErrors.set(true)
    }
}

dependencies {
    testImplementation(kotlin("test"))
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testRuntimeOnly(libs.junit.platform.launcher)
    if (providers.gradleProperty("noGoogleSelfTest").isPresent) {
        implementation("com.google.android.gms:play-services-location:21.3.0")
    }
}

tasks.test {
    useJUnitPlatform()
    // Recorded OJP answers and the prototype's outputs, shared with the prototype's tests
    val fixtures = rootProject.layout.projectDirectory.dir("../tests/fixtures").asFile
    inputs.dir(fixtures).withPropertyName("fixtures").withPathSensitivity(PathSensitivity.RELATIVE)
    systemProperty("spt.fixtures", fixtures.absolutePath)
    testLogging {
        events("failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
