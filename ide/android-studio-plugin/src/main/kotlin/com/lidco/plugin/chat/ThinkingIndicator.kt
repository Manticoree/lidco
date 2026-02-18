package com.lidco.plugin.chat

import java.awt.BorderLayout
import java.awt.Color
import java.awt.Font
import javax.swing.*

/**
 * A thinking indicator panel that shows an animated spinner with elapsed time.
 * Similar to Claude Code's thinking timer.
 *
 * Displays:  ● Routing... (3s)
 */
class ThinkingIndicator : JPanel(BorderLayout()) {

    private val label = JLabel()
    private val timer: Timer
    private var startTime = System.currentTimeMillis()
    private var status = "Thinking"
    private var frameIndex = 0

    private val spinnerFrames = arrayOf("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    private val fallbackFrames = arrayOf("|", "/", "-", "\\")

    init {
        isOpaque = false
        background = Color(0x1E, 0x1E, 0x2E)

        label.foreground = Color(0x89, 0xB4, 0xFA)
        label.font = Font("Monospaced", Font.PLAIN, 12)
        label.border = BorderFactory.createEmptyBorder(6, 10, 6, 10)
        add(label, BorderLayout.WEST)

        updateLabel()

        timer = Timer(250) {
            frameIndex = (frameIndex + 1) % spinnerFrames.size
            updateLabel()
        }
    }

    fun start() {
        startTime = System.currentTimeMillis()
        status = "Thinking"
        frameIndex = 0
        isVisible = true
        timer.start()
        updateLabel()
    }

    fun stop() {
        timer.stop()
        isVisible = false
    }

    fun updateStatus(newStatus: String) {
        status = newStatus
        updateLabel()
    }

    fun updateStatus(newStatus: String, serverElapsed: Double) {
        status = newStatus
        updateLabel()
    }

    private fun updateLabel() {
        val elapsed = (System.currentTimeMillis() - startTime) / 1000
        val elapsedStr = if (elapsed < 60) {
            "${elapsed}s"
        } else {
            "${elapsed / 60}m ${elapsed % 60}s"
        }

        val frame = try {
            spinnerFrames[frameIndex]
        } catch (_: Exception) {
            fallbackFrames[frameIndex % fallbackFrames.size]
        }

        label.text = "  $frame $status ($elapsedStr)"
        revalidate()
        repaint()
    }
}
