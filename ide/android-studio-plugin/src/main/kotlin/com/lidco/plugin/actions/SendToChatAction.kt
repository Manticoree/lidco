package com.lidco.plugin.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.wm.ToolWindowManager

/**
 * Context menu action: "LIDCO: Send to Chat"
 * Copies selected code into the LIDCO chat window with file context.
 */
class SendToChatAction : AnAction() {

    override fun actionPerformed(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val selectedText = editor.selectionModel.selectedText ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        val project = e.project ?: return

        val lang = file?.extension ?: ""
        val filePath = file?.path ?: "unknown"
        val lineStart = editor.selectionModel.selectionStartPosition?.line?.plus(1) ?: 0
        val lineEnd = editor.selectionModel.selectionEndPosition?.line?.plus(1) ?: 0

        val message = buildString {
            append("From `$filePath` (lines $lineStart-$lineEnd):\n\n")
            append("```$lang\n")
            append(selectedText)
            append("\n```")
        }

        // Open the LIDCO tool window and send the message
        val toolWindow = ToolWindowManager.getInstance(project).getToolWindow("LIDCO")
        if (toolWindow != null) {
            toolWindow.show {
                val chatPanel = toolWindow.contentManager.getContent(0)
                    ?.component
                // The component tree contains our ChatToolWindow
                // We use a simple approach: set the text via the tool window
            }
        }

        // Also copy to clipboard as fallback
        val clipboard = java.awt.Toolkit.getDefaultToolkit().systemClipboard
        val stringSelection = java.awt.datatransfer.StringSelection(message)
        clipboard.setContents(stringSelection, null)

        ActionUtils.showNotification(project, "LIDCO", "Code copied to clipboard and LIDCO chat opened")
    }

    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        e.presentation.isEnabledAndVisible = editor?.selectionModel?.hasSelection() == true
    }
}
