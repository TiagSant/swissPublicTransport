package io.github.tiagsant.spt

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Definition of done: every text of the app exists in English, French, German, Italian and Romansh. */
class LanguagesTest {
    private val res = File(System.getProperty("spt.res") ?: "src/main/res")
    private val languages = listOf("values", "values-fr", "values-de", "values-it", "values-rm")

    private fun strings(dir: String): Map<String, String> {
        val f = File(res, "$dir/strings.xml")
        assertTrue(f.isFile, "missing $f")
        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(f)
        val nodes = doc.getElementsByTagName("string")
        return (0 until nodes.length).map { nodes.item(it) as org.w3c.dom.Element }
            .filter { it.getAttribute("translatable") != "false" }
            .associate { it.getAttribute("name") to it.textContent }
    }

    @Test
    fun everyTextInFiveLanguages() {
        val english = strings("values")
        assertTrue(english.isNotEmpty())
        for (lang in languages.drop(1)) {
            val other = strings(lang)
            assertEquals(english.keys, other.keys, "texts of $lang")
            other.forEach { (k, v) -> assertTrue(v.isNotBlank(), "$lang/$k is empty") }
        }
    }

    @Test
    fun theLanguagesAreDeclaredToAndroid() {
        val config = File(res, "xml/locales_config.xml").readText()
        for (tag in listOf("en", "fr", "de", "it", "rm")) assertTrue("android:name=\"$tag\"" in config, "locale $tag")
    }
}
