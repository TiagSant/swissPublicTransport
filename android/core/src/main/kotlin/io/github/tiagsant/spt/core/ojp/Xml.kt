package io.github.tiagsant.spt.core.ojp

import org.w3c.dom.Document
import org.w3c.dom.Element
import org.w3c.dom.Node
import org.xml.sax.ErrorHandler
import org.xml.sax.InputSource
import org.xml.sax.SAXParseException
import java.io.StringReader
import javax.xml.XMLConstants
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Namespace-agnostic reading of OJP answers, with the same helpers as `assets/ojp.js` (`kids`, `el`, `txt`, `all`):
 * elements are matched by local name, whatever their prefix.
 */
internal object Xml {
    private const val XML_NS = "http://www.w3.org/XML/1998/namespace"

    fun parse(xml: String): Document {
        val factory = DocumentBuilderFactory.newInstance().apply {
            isNamespaceAware = true
            isExpandEntityReferences = false
            // No DOCTYPE, no external entities: answers come from the network
            runCatching { setFeature("http://apache.org/xml/features/disallow-doctype-decl", true) }
            runCatching { setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true) }
        }
        val builder = factory.newDocumentBuilder().apply { setErrorHandler(Silent) }
        return try {
            builder.parse(InputSource(StringReader(xml)))
        } catch (e: Exception) {
            throw OjpException.Malformed("unreadable XML answer: ${e.message}", e)
        }
    }

    /** Child elements named [name]. */
    fun Element?.kids(name: String): List<Element> {
        if (this == null) return emptyList()
        val out = ArrayList<Element>()
        var n: Node? = firstChild
        while (n != null) {
            if (n is Element && n.localName == name) out += n
            n = n.nextSibling
        }
        return out
    }

    /** The element at a path of child names ("Mode/PtMode"), or `null`. */
    fun Element?.el(path: String): Element? {
        var node: Element? = this
        for (name in path.split('/')) node = node.kids(name).firstOrNull() ?: return null
        return node
    }

    /** Text at a path: the `Text` child's when there is one (OJP's internationalised texts), trimmed; "" when absent. */
    fun Element?.txt(path: String? = null): String {
        val e = (if (path == null) this else el(path)) ?: return ""
        return (e.kids("Text").firstOrNull() ?: e).textContent.trim()
    }

    /** Every element named [name] in the document, in document order. */
    fun Node.all(name: String): List<Element> {
        val list = when (this) {
            is Document -> getElementsByTagNameNS("*", name)
            is Element -> getElementsByTagNameNS("*", name)
            else -> return emptyList()
        }
        return (0 until list.length).map { list.item(it) as Element }
    }

    /** Errors become exceptions (caught in [parse]) instead of lines on the console. */
    private object Silent : ErrorHandler {
        override fun warning(e: SAXParseException) = Unit
        override fun error(e: SAXParseException) = throw e
        override fun fatalError(e: SAXParseException) = throw e
    }

    fun Element.lang(): String = getAttributeNS(XML_NS, "lang").ifEmpty { getAttribute("xml:lang") }
}
