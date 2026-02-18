package com.lidco.plugin.api

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.lidco.plugin.settings.LidcoSettings
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * HTTP client for the LIDCO server API.
 *
 * All blocking methods run on OkHttp's dispatcher threads —
 * callers should invoke from a background thread or coroutine.
 */
class LidcoClient {

    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val sseFactory: EventSource.Factory = EventSources.createFactory(client)

    // ── Helpers ────────────────────────────────────────────────────────────

    private fun baseUrl(): String = LidcoSettings.getInstance().serverUrl.trimEnd('/')

    private fun authHeaders(): Headers {
        val builder = Headers.Builder()
        val token = LidcoSettings.getInstance().apiToken
        if (token.isNotBlank()) {
            builder.add("Authorization", "Bearer $token")
        }
        return builder.build()
    }

    private fun postJson(path: String, body: Any): Request {
        val json = gson.toJson(body)
        return Request.Builder()
            .url("${baseUrl()}$path")
            .headers(authHeaders())
            .post(json.toRequestBody(jsonMediaType))
            .build()
    }

    private fun get(path: String): Request {
        return Request.Builder()
            .url("${baseUrl()}$path")
            .headers(authHeaders())
            .build()
    }

    private inline fun <reified T> execute(request: Request): T {
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                val errorBody = response.body?.string() ?: ""
                throw LidcoApiException(response.code, errorBody)
            }
            val body = response.body?.string()
                ?: throw LidcoApiException(response.code, "Empty response body")
            return gson.fromJson(body, T::class.java)
        }
    }

    // ── Public API ─────────────────────────────────────────────────────────

    /** Check server health. Returns true if reachable. */
    fun isConnected(): Boolean {
        return try {
            val request = get("/health")
            client.newCall(request).execute().use { it.isSuccessful }
        } catch (_: IOException) {
            false
        }
    }

    /** Get server status. */
    fun status(): StatusResponse = execute(get("/api/status"))

    /** List available agents. */
    fun agents(): List<AgentInfo> {
        val request = get("/api/agents")
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw LidcoApiException(response.code, response.body?.string() ?: "")
            }
            val body = response.body?.string() ?: "[]"
            val type = object : TypeToken<List<AgentInfo>>() {}.type
            return gson.fromJson(body, type)
        }
    }

    /** Send a chat message and get a full response. */
    fun chat(request: ChatRequest): ChatResponse = execute(postJson("/api/chat", request))

    /** Send a chat message with SSE streaming. */
    fun chatStream(request: ChatRequest, listener: EventSourceListener): EventSource {
        val httpRequest = Request.Builder()
            .url("${baseUrl()}/api/chat/stream")
            .headers(authHeaders())
            .post(gson.toJson(request).toRequestBody(jsonMediaType))
            .build()
        return sseFactory.newEventSource(httpRequest, listener)
    }

    /** Request inline code completion. */
    fun complete(request: CompleteRequest): CompleteResponse =
        execute(postJson("/api/complete", request))

    /** Request a code review. */
    fun review(request: ReviewRequest): ReviewResponse =
        execute(postJson("/api/review", request))

    /** Request a code explanation. */
    fun explain(request: ExplainRequest): ExplainResponse =
        execute(postJson("/api/explain", request))
}

class LidcoApiException(val statusCode: Int, message: String) : RuntimeException(
    "LIDCO API error ($statusCode): $message"
)
