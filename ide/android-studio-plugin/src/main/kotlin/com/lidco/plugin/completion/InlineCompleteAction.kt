package com.lidco.plugin.completion

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.diagnostic.Logger
import com.lidco.plugin.api.CompleteRequest
import com.lidco.plugin.api.LidcoClient

/**
 * Action triggered by Alt+L to insert an inline AI completion at cursor.
 */
class InlineCompleteAction : AnAction() {

    private val log = Logger.getInstance(InlineCompleteAction::class.java)
    private val client = LidcoClient()

    override fun actionPerformed(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val project = e.project ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: return
        val document = editor.document
        val offset = editor.caretModel.offset
        val lineNumber = document.getLineNumber(offset)
        val lineStart = document.getLineStartOffset(lineNumber)
        val column = offset - lineStart

        val request = CompleteRequest(
            file_path = file.path,
            content = document.text,
            cursor_line = lineNumber,
            cursor_column = column,
            language = file.extension ?: "",
        )

        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val response = client.complete(request)
                if (response.completion.isNotBlank()) {
                    ApplicationManager.getApplication().invokeLater {
                        WriteCommandAction.runWriteCommandAction(project) {
                            document.insertString(offset, response.completion)
                        }
                    }
                }
            } catch (ex: Exception) {
                log.info("Inline completion failed: ${ex.message}")
            }
        }
    }
}
