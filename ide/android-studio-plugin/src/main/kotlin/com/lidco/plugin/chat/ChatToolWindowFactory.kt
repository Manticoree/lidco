package com.lidco.plugin.chat

import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory

/**
 * Factory for the LIDCO Chat tool window.
 * Registered in plugin.xml as a right-side panel.
 */
class ChatToolWindowFactory : ToolWindowFactory, DumbAware {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val chatPanel = ChatToolWindow(project)
        val content = ContentFactory.getInstance().createContent(chatPanel.component, "Chat", false)
        toolWindow.contentManager.addContent(content)
    }
}
