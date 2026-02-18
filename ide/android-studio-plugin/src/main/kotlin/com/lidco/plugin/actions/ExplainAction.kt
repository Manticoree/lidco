package com.lidco.plugin.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.lidco.plugin.api.ExplainRequest
import com.lidco.plugin.api.LidcoClient

/**
 * Context menu action: "LIDCO: Explain Code"
 */
class ExplainAction : AnAction() {

    private val log = Logger.getInstance(ExplainAction::class.java)

    override fun actionPerformed(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val selectedText = editor.selectionModel.selectedText ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        val project = e.project ?: return

        val request = ExplainRequest(
            code = selectedText,
            file_path = file?.path ?: "",
            language = file?.extension ?: "",
        )

        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val response = LidcoClient().explain(request)
                ActionUtils.showResultInChat(project, "Explanation", response.explanation)
            } catch (ex: Exception) {
                log.warn("Explain failed: ${ex.message}")
                ActionUtils.showNotification(project, "LIDCO Explain Error", ex.message ?: "Unknown error")
            }
        }
    }

    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        e.presentation.isEnabledAndVisible = editor?.selectionModel?.hasSelection() == true
    }
}
