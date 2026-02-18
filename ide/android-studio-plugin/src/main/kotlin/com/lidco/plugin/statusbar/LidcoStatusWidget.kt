package com.lidco.plugin.statusbar

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.StatusBar
import com.intellij.openapi.wm.StatusBarWidget
import com.intellij.openapi.wm.StatusBarWidgetFactory
import com.intellij.util.Consumer
import com.lidco.plugin.api.LidcoClient
import java.awt.Component
import java.awt.event.MouseEvent
import javax.swing.Timer

/**
 * Status bar widget showing LIDCO connection status and current model.
 */
class LidcoStatusWidgetFactory : StatusBarWidgetFactory {

    override fun getId(): String = "LidcoStatusWidget"
    override fun getDisplayName(): String = "LIDCO Status"
    override fun isAvailable(project: Project): Boolean = true

    override fun createWidget(project: Project): StatusBarWidget {
        return LidcoStatusWidget(project)
    }
}

private class LidcoStatusWidget(private val project: Project) : StatusBarWidget,
    StatusBarWidget.TextPresentation {

    private val log = Logger.getInstance(LidcoStatusWidget::class.java)
    private val client = LidcoClient()

    private var statusBar: StatusBar? = null
    private var connected = false
    private var currentModel = ""
    private val refreshTimer: Timer

    init {
        // Poll server status every 30 seconds
        refreshTimer = Timer(30_000) { refreshStatus() }
        refreshTimer.isRepeats = true
        refreshTimer.start()
        refreshStatus()
    }

    override fun ID(): String = "LidcoStatusWidget"

    override fun getPresentation(): StatusBarWidget.WidgetPresentation = this

    override fun install(statusBar: StatusBar) {
        this.statusBar = statusBar
    }

    override fun dispose() {
        refreshTimer.stop()
    }

    // ── TextPresentation ───────────────────────────────────────────────────

    override fun getText(): String {
        return if (connected) "LIDCO: $currentModel" else "LIDCO: offline"
    }

    override fun getAlignment(): Float = Component.LEFT_ALIGNMENT

    override fun getTooltipText(): String {
        return if (connected) {
            "LIDCO connected — model: $currentModel\nClick to refresh"
        } else {
            "LIDCO server not running\nStart with: lidco serve"
        }
    }

    override fun getClickConsumer(): Consumer<MouseEvent> = Consumer {
        refreshStatus()
    }

    // ── Refresh ────────────────────────────────────────────────────────────

    private fun refreshStatus() {
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val status = client.status()
                connected = true
                currentModel = status.model
            } catch (_: Exception) {
                connected = false
                currentModel = ""
            }
            statusBar?.updateWidget(ID())
        }
    }
}
