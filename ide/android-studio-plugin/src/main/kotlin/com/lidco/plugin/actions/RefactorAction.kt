package com.lidco.plugin.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.lidco.plugin.api.ChatRequest
import com.lidco.plugin.api.LidcoClient

/**
 * Context menu action: "LIDCO: Refactor"
 * Sends selected code to the refactor agent for suggestions.
 */
class RefactorAction : AnAction() {

    private val log = Logger.getInstance(RefactorAction::class.java)

    override fun actionPerformed(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val selectedText = editor.selectionModel.selectedText ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        val project = e.project ?: return

        val lang = file?.extension ?: ""
        val message = "Refactor the following ${lang} code. " +
                "Suggest improvements for readability, performance, and best practices:\n\n" +
                "```${lang}\n${selectedText}\n```"

        val request = ChatRequest(message = message, agent = "refactor")

        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val response = LidcoClient().chat(request)
                ActionUtils.showResultInChat(project, "Refactor Suggestions", response.content)
            } catch (ex: Exception) {
                log.warn("Refactor failed: ${ex.message}")
                ActionUtils.showNotification(project, "LIDCO Refactor Error", ex.message ?: "Unknown error")
            }
        }
    }

    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        e.presentation.isEnabledAndVisible = editor?.selectionModel?.hasSelection() == true
    }
}
