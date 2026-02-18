package com.lidco.plugin.settings

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.openapi.options.Configurable
import com.intellij.util.xmlb.XmlSerializerUtil
import javax.swing.*

/**
 * Persistent application-level settings for the LIDCO plugin.
 */
@State(
    name = "com.lidco.plugin.settings.LidcoSettings",
    storages = [Storage("LidcoPlugin.xml")]
)
class LidcoSettings : PersistentStateComponent<LidcoSettings> {

    var serverUrl: String = "http://127.0.0.1:8321"
    var apiToken: String = ""
    var defaultAgent: String = ""
    var streamingEnabled: Boolean = true

    override fun getState(): LidcoSettings = this

    override fun loadState(state: LidcoSettings) {
        XmlSerializerUtil.copyBean(state, this)
    }

    companion object {
        fun getInstance(): LidcoSettings {
            return ApplicationManager.getApplication()
                .getService(LidcoSettings::class.java)
        }
    }
}

/**
 * Settings UI accessible from Settings > Tools > LIDCO.
 */
class LidcoSettingsConfigurable : Configurable {

    private var serverUrlField: JTextField? = null
    private var apiTokenField: JTextField? = null
    private var defaultAgentField: JTextField? = null
    private var streamingCheckbox: JCheckBox? = null

    override fun getDisplayName(): String = "LIDCO"

    override fun createComponent(): JComponent {
        val panel = JPanel()
        panel.layout = BoxLayout(panel, BoxLayout.Y_AXIS)

        val settings = LidcoSettings.getInstance()

        serverUrlField = JTextField(settings.serverUrl, 40).also {
            panel.add(labeledRow("Server URL:", it))
        }
        apiTokenField = JTextField(settings.apiToken, 40).also {
            panel.add(labeledRow("API Token:", it))
        }
        defaultAgentField = JTextField(settings.defaultAgent, 20).also {
            panel.add(labeledRow("Default Agent:", it))
        }
        streamingCheckbox = JCheckBox("Enable SSE streaming", settings.streamingEnabled).also {
            panel.add(it)
        }

        return panel
    }

    override fun isModified(): Boolean {
        val s = LidcoSettings.getInstance()
        return serverUrlField?.text != s.serverUrl
                || apiTokenField?.text != s.apiToken
                || defaultAgentField?.text != s.defaultAgent
                || streamingCheckbox?.isSelected != s.streamingEnabled
    }

    override fun apply() {
        val s = LidcoSettings.getInstance()
        s.serverUrl = serverUrlField?.text ?: s.serverUrl
        s.apiToken = apiTokenField?.text ?: s.apiToken
        s.defaultAgent = defaultAgentField?.text ?: s.defaultAgent
        s.streamingEnabled = streamingCheckbox?.isSelected ?: s.streamingEnabled
    }

    override fun reset() {
        val s = LidcoSettings.getInstance()
        serverUrlField?.text = s.serverUrl
        apiTokenField?.text = s.apiToken
        defaultAgentField?.text = s.defaultAgent
        streamingCheckbox?.isSelected = s.streamingEnabled
    }

    private fun labeledRow(label: String, field: JComponent): JPanel {
        val row = JPanel()
        row.layout = BoxLayout(row, BoxLayout.X_AXIS)
        row.add(JLabel(label))
        row.add(Box.createHorizontalStrut(8))
        row.add(field)
        row.alignmentX = JPanel.LEFT_ALIGNMENT
        return row
    }
}
