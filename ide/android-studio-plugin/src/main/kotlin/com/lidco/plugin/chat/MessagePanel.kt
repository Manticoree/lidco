package com.lidco.plugin.chat

import org.commonmark.parser.Parser
import org.commonmark.renderer.html.HtmlRenderer
import java.awt.BorderLayout
import java.awt.Color
import java.awt.Font
import javax.swing.*
import javax.swing.text.html.HTMLEditorKit
import javax.swing.text.html.StyleSheet

/**
 * Panel that renders chat messages with basic Markdown support.
 * Uses CommonMark to convert Markdown to HTML for display in a JEditorPane.
 */
class MessagePanel {

    private val messagesContainer = JPanel()
    private val mdParser: Parser = Parser.builder().build()
    private val htmlRenderer: HtmlRenderer = HtmlRenderer.builder().build()

    /** Currently streaming message label (null when not streaming). */
    private var streamingPane: JEditorPane? = null

    /** Active tool event panels keyed by tool name for result updates. */
    private val activeToolPanels = mutableMapOf<String, ToolEventPanel>()

    /** Thinking indicator with timer. */
    val thinkingIndicator = ThinkingIndicator()

    val scrollPane: JScrollPane

    init {
        messagesContainer.layout = BoxLayout(messagesContainer, BoxLayout.Y_AXIS)
        messagesContainer.background = Color(0x1E, 0x1E, 0x2E) // dark background

        thinkingIndicator.isVisible = false
        messagesContainer.add(thinkingIndicator)

        scrollPane = JScrollPane(messagesContainer)
        scrollPane.verticalScrollBarPolicy = JScrollPane.VERTICAL_SCROLLBAR_AS_NEEDED
        scrollPane.horizontalScrollBarPolicy = JScrollPane.HORIZONTAL_SCROLLBAR_NEVER
    }

    /** Add a fully rendered message bubble. */
    fun addMessage(sender: String, markdown: String) {
        val html = renderMarkdown(markdown)
        val pane = createHtmlPane(sender, html)
        // Insert before the thinking indicator (which is always last)
        val idx = messagesContainer.componentCount - 1
        messagesContainer.add(pane, idx.coerceAtLeast(0))
        messagesContainer.add(Box.createVerticalStrut(6), idx.coerceAtLeast(0) + 1)
        scrollToBottom()
    }

    /** Update a streaming message in place (replaces content each call). */
    fun updateStreamingMessage(sender: String, markdown: String) {
        // Hide thinking indicator once content starts arriving
        thinkingIndicator.stop()

        val html = renderMarkdown(markdown)
        if (streamingPane == null) {
            streamingPane = createHtmlPane(sender, html)
            val idx = messagesContainer.componentCount - 1
            messagesContainer.add(streamingPane, idx.coerceAtLeast(0))
            messagesContainer.add(Box.createVerticalStrut(6), idx.coerceAtLeast(0) + 1)
        } else {
            streamingPane!!.text = wrapHtml(sender, html)
        }
        scrollToBottom()
    }

    /** Finalize the current streaming message. */
    fun finalizeStreamingMessage() {
        streamingPane = null
        activeToolPanels.clear()
    }

    /** Clean up streaming state on error or interruption. */
    fun cleanupStreaming() {
        streamingPane = null
        activeToolPanels.clear()
    }

    /** Add a tool-start event panel inline during streaming. */
    fun addToolStart(toolName: String, args: Map<String, String>) {
        // Hide thinking indicator once tool activity starts
        thinkingIndicator.stop()

        // Finalize the current streaming text pane so new text goes after the tool block
        streamingPane = null

        val keyArg = ToolEventPanel.extractKeyArg(toolName, args)
        val panel = ToolEventPanel(toolName, keyArg)
        val idx = messagesContainer.componentCount - 1
        messagesContainer.add(panel, idx.coerceAtLeast(0))
        activeToolPanels[toolName] = panel
        scrollToBottom()
    }

    /** Update a tool-end event on its corresponding panel. */
    fun addToolEnd(toolName: String, success: Boolean, output: String, error: String) {
        val panel = activeToolPanels.remove(toolName)
        if (panel != null) {
            if (success) {
                val brief = ToolEventPanel.briefResult(toolName, output)
                panel.showSuccess(brief)
            } else {
                panel.showError(error.ifEmpty { "failed" })
            }
        }
        scrollToBottom()
    }

    /** Show a summary panel at the end of a streaming response. */
    fun addSummary(modelUsed: String, iterations: Int, totalTokens: Int, elapsed: Double) {
        val tokensStr = if (totalTokens >= 1000) "${totalTokens / 1000.0}k" else "$totalTokens"
        val text = "[$modelUsed | $iterations iterations | $tokensStr tokens | ${elapsed}s]"

        val label = JLabel(text)
        label.font = java.awt.Font("Monospaced", java.awt.Font.PLAIN, 10)
        label.foreground = Color(0x6C, 0x70, 0x86)
        label.border = BorderFactory.createEmptyBorder(4, 10, 8, 10)

        val idx = messagesContainer.componentCount - 1
        messagesContainer.add(label, idx.coerceAtLeast(0))
        scrollToBottom()
    }

    // ── Private helpers ────────────────────────────────────────────────────

    private fun renderMarkdown(markdown: String): String {
        val document = mdParser.parse(markdown)
        return htmlRenderer.render(document)
    }

    private fun wrapHtml(sender: String, bodyHtml: String): String {
        return """
            <html><body style="font-family: sans-serif; font-size: 12px; color: #CDD6F4; margin: 4px;">
            <b style="color: #89B4FA;">$sender</b><br/>
            $bodyHtml
            </body></html>
        """.trimIndent()
    }

    private fun createHtmlPane(sender: String, bodyHtml: String): JEditorPane {
        val pane = JEditorPane()
        pane.contentType = "text/html"
        pane.isEditable = false
        pane.isOpaque = false
        pane.background = Color(0x31, 0x32, 0x44)

        val kit = HTMLEditorKit()
        val styles = StyleSheet()
        styles.addRule("body { font-family: sans-serif; font-size: 12px; color: #CDD6F4; margin: 6px; }")
        styles.addRule("pre { background: #181825; padding: 6px; border-radius: 4px; overflow-x: auto; }")
        styles.addRule("code { font-family: monospace; background: #181825; padding: 1px 3px; }")
        kit.styleSheet = styles
        pane.editorKit = kit

        pane.text = wrapHtml(sender, bodyHtml)
        pane.caretPosition = 0

        // Limit height to avoid infinite expansion
        pane.maximumSize = java.awt.Dimension(Int.MAX_VALUE, Int.MAX_VALUE)

        return pane
    }

    private fun scrollToBottom() {
        SwingUtilities.invokeLater {
            val vsb = scrollPane.verticalScrollBar
            vsb.value = vsb.maximum
            messagesContainer.revalidate()
            messagesContainer.repaint()
        }
    }
}
