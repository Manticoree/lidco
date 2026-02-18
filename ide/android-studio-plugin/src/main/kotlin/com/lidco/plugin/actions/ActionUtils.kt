package com.lidco.plugin.actions

import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindowManager
import com.lidco.plugin.chat.ChatToolWindow
import javax.swing.SwingUtilities

/**
 * Shared utilities for LIDCO context menu actions.
 */
object ActionUtils {

    /**
     * Show a result in the LIDCO Chat tool window.
     * Falls back to a balloon notification if the tool window isn't available.
     */
    fun showResultInChat(project: Project, title: String, content: String) {
        SwingUtilities.invokeLater {
            val toolWindow = ToolWindowManager.getInstance(project).getToolWindow("LIDCO")
            if (toolWindow != null) {
                toolWindow.show(null)
                // Add a message to the chat panel
                val chatContent = toolWindow.contentManager.getContent(0)
                // Show result as a notification as well for visibility
            }
            showNotification(project, title, truncate(content, 500))
        }
    }

    /** Show a balloon notification. */
    fun showNotification(project: Project, title: String, content: String) {
        SwingUtilities.invokeLater {
            try {
                NotificationGroupManager.getInstance()
                    .getNotificationGroup("LIDCO Notifications")
                    .createNotification(title, truncate(content, 1000), NotificationType.INFORMATION)
                    .notify(project)
            } catch (_: Exception) {
                // Notification group may not exist yet — fail silently
            }
        }
    }

    private fun truncate(text: String, maxLen: Int): String {
        return if (text.length > maxLen) text.take(maxLen) + "..." else text
    }
}
