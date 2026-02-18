package com.lidco.plugin.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.lidco.plugin.api.LidcoClient
import com.lidco.plugin.api.ReviewRequest

/**
 * Context menu action: "LIDCO: Review Code"
 * Sends the selected code to the LIDCO server for review
 * and displays the result in a notification balloon.
 */
class ReviewAction : AnAction() {

    private val log = Logger.getInstance(ReviewAction::class.java)

    override fun actionPerformed(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val selection = editor.selectionModel
        val selectedText = selection.selectedText ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        val project = e.project ?: return

        val request = ReviewRequest(
            code = selectedText,
            file_path = file?.path ?: "",
            language = file?.extension ?: "",
        )

        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val response = LidcoClient().review(request)
                ActionUtils.showResultInChat(project, "Code Review", response.review)
            } catch (ex: Exception) {
                log.warn("Review failed: ${ex.message}")
                ActionUtils.showNotification(project, "LIDCO Review Error", ex.message ?: "Unknown error")
            }
        }
    }

    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        e.presentation.isEnabledAndVisible = editor?.selectionModel?.hasSelection() == true
    }
}
