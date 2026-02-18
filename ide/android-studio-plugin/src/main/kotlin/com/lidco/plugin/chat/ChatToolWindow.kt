package com.lidco.plugin.chat

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.Project
import com.lidco.plugin.api.ChatRequest
import com.lidco.plugin.api.LidcoApiException
import com.lidco.plugin.api.LidcoClient
import com.lidco.plugin.api.SseDoneEvent
import com.lidco.plugin.api.SseToolEndEvent
import com.lidco.plugin.api.SseToolStartEvent
import com.lidco.plugin.settings.LidcoSettings
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import java.awt.BorderLayout
import java.awt.Dimension
import java.awt.event.KeyAdapter
import java.awt.event.KeyEvent
import javax.swing.*

/**
 * Main chat panel displayed in the LIDCO tool window.
 * Supports both blocking and SSE-streaming chat modes.
 */
class ChatToolWindow(private val project: Project) {

    private val log = Logger.getInstance(ChatToolWindow::class.java)
    private val client = LidcoClient()
    private val gson = Gson()

    private val messagesPanel = MessagePanel()
    private val inputField = JTextArea(3, 0)
    private val sendButton = JButton("Send")
    private val agentSelector = JComboBox<String>()

    val component: JComponent

    init {
        // Load agents list in background
        loadAgents()

        // Input area
        inputField.lineWrap = true
        inputField.wrapStyleWord = true
        inputField.addKeyListener(object : KeyAdapter() {
            override fun keyPressed(e: KeyEvent) {
                if (e.keyCode == KeyEvent.VK_ENTER && !e.isShiftDown) {
                    e.consume()
                    sendMessage()
                }
            }
        })

        sendButton.addActionListener { sendMessage() }

        val inputPanel = JPanel(BorderLayout(4, 0))
        inputPanel.add(JScrollPane(inputField), BorderLayout.CENTER)

        val controlsPanel = JPanel(BorderLayout(4, 0))
        controlsPanel.add(agentSelector, BorderLayout.WEST)
        controlsPanel.add(sendButton, BorderLayout.EAST)
        inputPanel.add(controlsPanel, BorderLayout.SOUTH)

        // Main layout
        val mainPanel = JPanel(BorderLayout(0, 4))
        mainPanel.preferredSize = Dimension(400, 600)
        mainPanel.add(messagesPanel.scrollPane, BorderLayout.CENTER)
        mainPanel.add(inputPanel, BorderLayout.SOUTH)

        component = mainPanel
    }

    /** Append a message to the chat (from external actions). */
    fun appendUserMessage(message: String) {
        inputField.text = message
        sendMessage()
    }

    private fun loadAgents() {
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val agents = client.agents()
                SwingUtilities.invokeLater {
                    agentSelector.removeAllItems()
                    agentSelector.addItem("auto")
                    agents.forEach { agentSelector.addItem(it.name) }
                }
            } catch (e: Exception) {
                log.info("Could not load agents: ${e.message}")
                SwingUtilities.invokeLater {
                    agentSelector.removeAllItems()
                    agentSelector.addItem("auto")
                }
            }
        }
    }

    private fun sendMessage() {
        val text = inputField.text.trim()
        if (text.isEmpty()) return

        inputField.text = ""
        inputField.isEnabled = false
        sendButton.isEnabled = false

        messagesPanel.addMessage("You", text)
        messagesPanel.thinkingIndicator.start()

        val selectedAgent = agentSelector.selectedItem?.toString()
        val agent = if (selectedAgent == "auto") null else selectedAgent

        val request = ChatRequest(message = text, agent = agent)
        val settings = LidcoSettings.getInstance()

        if (settings.streamingEnabled) {
            streamChat(request)
        } else {
            blockingChat(request)
        }
    }

    private fun blockingChat(request: ChatRequest) {
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val response = client.chat(request)
                SwingUtilities.invokeLater {
                    messagesPanel.thinkingIndicator.stop()
                    messagesPanel.addMessage("LIDCO (${response.agent})", response.content)
                    enableInput()
                }
            } catch (e: LidcoApiException) {
                SwingUtilities.invokeLater {
                    messagesPanel.thinkingIndicator.stop()
                    messagesPanel.addMessage("Error", e.message ?: "Unknown error")
                    enableInput()
                }
            } catch (e: Exception) {
                SwingUtilities.invokeLater {
                    messagesPanel.thinkingIndicator.stop()
                    messagesPanel.addMessage("Error", "Connection failed: ${e.message}")
                    enableInput()
                }
            }
        }
    }

    private fun streamChat(request: ChatRequest) {
        val buffer = StringBuilder()

        client.chatStream(request, object : EventSourceListener() {
            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                when (type) {
                    "status" -> {
                        try {
                            val obj = gson.fromJson(data, JsonObject::class.java)
                            val status = obj.get("status")?.asString ?: "Thinking"
                            val elapsed = obj.get("elapsed")?.asDouble ?: 0.0
                            SwingUtilities.invokeLater {
                                messagesPanel.thinkingIndicator.updateStatus(status, elapsed)
                            }
                        } catch (e: Exception) { log.debug("Failed to parse status event", e) }
                    }
                    "token" -> {
                        try {
                            val obj = gson.fromJson(data, JsonObject::class.java)
                            val chunk = obj.get("text")?.asString ?: ""
                            buffer.append(chunk)
                            SwingUtilities.invokeLater {
                                messagesPanel.updateStreamingMessage("LIDCO", buffer.toString())
                            }
                        } catch (e: Exception) { log.debug("Failed to parse token event", e) }
                    }
                    "tool_start" -> {
                        try {
                            val event = gson.fromJson(data, SseToolStartEvent::class.java)
                            SwingUtilities.invokeLater {
                                messagesPanel.addToolStart(event.tool, event.args)
                            }
                        } catch (e: Exception) { log.debug("Failed to parse tool_start event", e) }
                    }
                    "tool_end" -> {
                        try {
                            val event = gson.fromJson(data, SseToolEndEvent::class.java)
                            SwingUtilities.invokeLater {
                                messagesPanel.addToolEnd(
                                    event.tool, event.success, event.output, event.error
                                )
                            }
                        } catch (e: Exception) { log.debug("Failed to parse tool_end event", e) }
                    }
                    "tool_call" -> {
                        // Legacy event — ignored when tool_start/tool_end are available
                    }
                    "done" -> {
                        try {
                            val event = gson.fromJson(data, SseDoneEvent::class.java)
                            SwingUtilities.invokeLater {
                                messagesPanel.thinkingIndicator.stop()
                                messagesPanel.finalizeStreamingMessage()
                                messagesPanel.addSummary(
                                    event.model_used,
                                    event.iterations,
                                    event.total_tokens,
                                    event.elapsed,
                                )
                                enableInput()
                            }
                        } catch (_: Exception) {
                            SwingUtilities.invokeLater {
                                messagesPanel.thinkingIndicator.stop()
                                messagesPanel.finalizeStreamingMessage()
                                enableInput()
                            }
                        }
                    }
                    "error" -> {
                        try {
                            val obj = gson.fromJson(data, JsonObject::class.java)
                            val msg = obj.get("message")?.asString ?: "Unknown error"
                            SwingUtilities.invokeLater {
                                messagesPanel.thinkingIndicator.stop()
                                messagesPanel.addMessage("Error", msg)
                                enableInput()
                            }
                        } catch (e: Exception) { log.debug("Failed to parse error event", e) }
                    }
                }
            }

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                SwingUtilities.invokeLater {
                    messagesPanel.thinkingIndicator.stop()
                    messagesPanel.cleanupStreaming()
                    val msg = t?.message ?: "Connection lost"
                    messagesPanel.addMessage("Error", msg)
                    enableInput()
                }
            }
        })
    }

    private fun enableInput() {
        inputField.isEnabled = true
        sendButton.isEnabled = true
        inputField.requestFocusInWindow()
    }
}
