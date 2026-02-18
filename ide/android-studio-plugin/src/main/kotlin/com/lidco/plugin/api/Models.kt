package com.lidco.plugin.api

/** Request/response data classes matching the LIDCO server API. */

// ── Requests ─────────────────────────────────────────────────────────────

data class ChatRequest(
    val message: String,
    val agent: String? = null,
    val context_files: List<String> = emptyList(),
)

data class CompleteRequest(
    val file_path: String,
    val content: String,
    val cursor_line: Int,
    val cursor_column: Int,
    val language: String = "",
    val max_tokens: Int = 256,
)

data class ReviewRequest(
    val code: String,
    val file_path: String = "",
    val language: String = "",
    val instructions: String = "",
)

data class ExplainRequest(
    val code: String,
    val file_path: String = "",
    val language: String = "",
)

// ── Responses ────────────────────────────────────────────────────────────

data class ChatResponse(
    val content: String,
    val agent: String,
    val model_used: String = "",
    val iterations: Int = 0,
    val tool_calls: List<Map<String, Any>> = emptyList(),
)

data class CompleteResponse(
    val completion: String,
    val model_used: String = "",
)

data class ReviewResponse(
    val review: String,
    val agent: String = "",
    val model_used: String = "",
)

data class ExplainResponse(
    val explanation: String,
    val agent: String = "",
    val model_used: String = "",
)

data class AgentInfo(
    val name: String,
    val description: String,
)

data class StatusResponse(
    val version: String,
    val status: String,
    val model: String,
    val agents: List<String>,
    val memory_entries: Int,
    val project_dir: String,
)

data class ErrorResponse(
    val error: String,
    val detail: String = "",
)

// ── SSE streaming event payloads ────────────────────────────────────────

data class SseToolStartEvent(
    val tool: String,
    val args: Map<String, String> = emptyMap(),
)

data class SseToolEndEvent(
    val tool: String,
    val success: Boolean = true,
    val output: String = "",
    val error: String = "",
)

data class SseDoneEvent(
    val agent: String = "",
    val model_used: String = "",
    val iterations: Int = 0,
    val tool_calls_count: Int = 0,
    val total_tokens: Int = 0,
    val elapsed: Double = 0.0,
)
