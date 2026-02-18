package com.lidco.plugin.chat

import java.awt.BorderLayout
import java.awt.Color
import java.awt.Dimension
import java.awt.Font
import javax.swing.BorderFactory
import javax.swing.BoxLayout
import javax.swing.JLabel
import javax.swing.JPanel

/**
 * A compact panel that displays a tool call event inline in the chat.
 *
 * Shows tool invocations like:
 *   ⚡ file_read src/main.py
 *   ✓ 45 lines
 * or on failure:
 *   ✗ File not found
 */
class ToolEventPanel(
    private val toolName: String,
    private val keyArg: String,
) : JPanel() {

    private val startLabel = JLabel()
    private val resultLabel = JLabel()
    private val monoFont = Font("Monospaced", Font.PLAIN, 11)

    init {
        layout = BoxLayout(this, BoxLayout.Y_AXIS)
        isOpaque = false
        border = BorderFactory.createEmptyBorder(2, 16, 2, 8)

        // Start line: ⚡ tool_name key_arg
        startLabel.font = monoFont
        startLabel.foreground = Color(0xF9, 0xE2, 0xAF) // yellow
        val argText = if (keyArg.isNotEmpty()) " $keyArg" else ""
        startLabel.text = "\u26A1 $toolName$argText"
        add(startLabel)

        // Result line (hidden until showResult is called)
        resultLabel.font = monoFont
        resultLabel.isVisible = false
        add(resultLabel)

        maximumSize = Dimension(Int.MAX_VALUE, preferredSize.height + 40)
    }

    /** Display a success result. */
    fun showSuccess(brief: String) {
        resultLabel.foreground = Color(0xA6, 0xE3, 0xA1) // green
        resultLabel.text = "\u2713 $brief"
        resultLabel.isVisible = true
        revalidate()
        repaint()
    }

    /** Display a failure result. */
    fun showError(message: String) {
        val truncated = if (message.length > 80) message.take(77) + "..." else message
        resultLabel.foreground = Color(0xF3, 0x8B, 0xA8) // red
        resultLabel.text = "\u2717 $truncated"
        resultLabel.isVisible = true
        revalidate()
        repaint()
    }

    companion object {
        /** Extract the most informative argument for display. */
        fun extractKeyArg(toolName: String, args: Map<String, String>): String {
            return when (toolName) {
                "file_read", "file_write", "file_edit" -> args["path"] ?: ""
                "bash" -> {
                    val cmd = args["command"] ?: ""
                    if (cmd.length > 60) cmd.take(57) + "..." else cmd
                }
                "grep", "glob" -> args["pattern"] ?: ""
                "git" -> args["subcommand"] ?: ""
                else -> ""
            }
        }

        /** Create a brief summary from a tool result. */
        fun briefResult(toolName: String, output: String): String {
            return when (toolName) {
                "file_read" -> "${output.count { it == '\n' }} lines"
                "file_write", "file_edit" -> "Applied edit"
                "bash" -> {
                    val lines = output.trim().split("\n")
                    if (lines.size <= 1) {
                        val text = lines.firstOrNull() ?: "done"
                        if (text.length > 80) text.take(77) + "..." else text
                    } else {
                        "${lines.size} lines of output"
                    }
                }
                "grep", "glob" -> {
                    val matches = output.trim().split("\n").filter { it.isNotEmpty() }
                    "${matches.size} matches"
                }
                "git" -> {
                    val text = output.trim()
                    if (text.length > 60) text.take(57) + "..." else text.ifEmpty { "done" }
                }
                else -> if (output.length > 60) output.take(57) + "..." else output.ifEmpty { "done" }
            }
        }
    }
}
