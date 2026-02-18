package com.lidco.plugin

import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.Project
import com.intellij.openapi.startup.ProjectActivity
import com.lidco.plugin.api.LidcoClient

/**
 * Plugin startup activity — runs when a project is opened.
 * Checks LIDCO server connectivity in the background.
 */
class LidcoStartupActivity : ProjectActivity {

    private val log = Logger.getInstance(LidcoStartupActivity::class.java)

    override suspend fun execute(project: Project) {
        val client = LidcoClient()
        val connected = try {
            client.isConnected()
        } catch (e: Exception) {
            log.warn("LIDCO server not reachable: ${e.message}")
            false
        }

        if (connected) {
            log.info("LIDCO server connected")
        } else {
            log.info("LIDCO server not running — start it with 'lidco serve'")
        }
    }
}
