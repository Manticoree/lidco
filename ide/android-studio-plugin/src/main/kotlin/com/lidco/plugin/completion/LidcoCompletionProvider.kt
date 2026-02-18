package com.lidco.plugin.completion

import com.intellij.codeInsight.completion.*
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.patterns.PlatformPatterns
import com.intellij.util.ProcessingContext
import com.lidco.plugin.api.CompleteRequest
import com.lidco.plugin.api.LidcoClient
import java.util.concurrent.Future
import java.util.concurrent.TimeUnit

/**
 * Completion contributor that provides AI-powered inline code completions
 * via the LIDCO server's /api/complete endpoint.
 */
class LidcoCompletionProvider : CompletionContributor() {

    init {
        extend(
            CompletionType.BASIC,
            PlatformPatterns.psiElement(),
            LidcoCompletionHandler(),
        )
    }
}

private class LidcoCompletionHandler : CompletionProvider<CompletionParameters>() {

    private val log = Logger.getInstance(LidcoCompletionHandler::class.java)
    private val client = LidcoClient()

    override fun addCompletions(
        parameters: CompletionParameters,
        context: ProcessingContext,
        result: CompletionResultSet
    ) {
        val editor = parameters.editor
        val document = editor.document
        val offset = parameters.offset
        val file = parameters.originalFile.virtualFile ?: return

        val content = document.text
        val lineNumber = document.getLineNumber(offset)
        val lineStart = document.getLineStartOffset(lineNumber)
        val column = offset - lineStart

        val request = CompleteRequest(
            file_path = file.path,
            content = content,
            cursor_line = lineNumber,
            cursor_column = column,
            language = file.extension ?: "",
        )

        // Run completion on pooled thread with timeout
        val future: Future<String?> = ApplicationManager.getApplication().executeOnPooledThread<String?> {
            try {
                val response = client.complete(request)
                response.completion
            } catch (e: Exception) {
                log.debug("LIDCO completion failed: ${e.message}")
                null
            }
        }

        try {
            val completion = future.get(5, TimeUnit.SECONDS)
            if (!completion.isNullOrBlank()) {
                val element = LookupElementBuilder.create(completion)
                    .withPresentableText(completion.lines().first())
                    .withTailText(" (LIDCO)", true)
                    .withTypeText("AI")
                    .bold()
                result.addElement(PrioritizedLookupElement.withPriority(element, -100.0))
            }
        } catch (_: Exception) {
            // Timeout or cancellation — silently skip
        }
    }
}
