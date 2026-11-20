package io.github.tiagsant.spt.core.ojp

import java.time.Duration

/** Why an OJP call failed. "No results" is not an error: it comes back as an empty answer with a notice. */
sealed class OjpException(message: String, cause: Throwable? = null) : Exception(message, cause) {
    /** 401 / 403: the key is missing, wrong or revoked. */
    class Unauthorized(val status: Int) : OjpException("OJP refused the key (HTTP $status)")

    /** 429: the key's limit is reached; try again after [retryAfter] when the server says. */
    class RateLimited(val retryAfter: Duration?) : OjpException("OJP request limit reached" + (retryAfter?.let { ", retry after ${it.seconds} s" } ?: ""))

    /** No answer in time. */
    class Timeout(cause: Throwable? = null) : OjpException("OJP did not answer in time", cause)

    /** The network failed before an answer (no connection, DNS, TLS…). */
    class Network(cause: Throwable) : OjpException("OJP unreachable: ${cause.message}", cause)

    /** Any other HTTP error. */
    class Http(val status: Int, val body: String) : OjpException("OJP answered HTTP $status")

    /** The answer is not readable OJP. */
    class Malformed(detail: String, cause: Throwable? = null) : OjpException(detail, cause)
}
