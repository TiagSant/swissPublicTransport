package io.github.tiagsant.spt.core

import java.io.File

/** The repository's recorded test data (`tests/fixtures`), shared with the prototype's tests. */
object Fixtures {
    val dir: File = File(System.getProperty("spt.fixtures") ?: "../../tests/fixtures").absoluteFile.also {
        require(it.isDirectory) { "fixtures not found at $it (set -Dspt.fixtures)" }
    }

    fun file(path: String): File = File(dir, path)

    fun text(path: String): String = file(path).readText()
}
