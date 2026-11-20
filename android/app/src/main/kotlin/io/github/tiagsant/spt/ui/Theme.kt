package io.github.tiagsant.spt.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Placeholder palette (Sprint 10): Swiss red accent; the look of lines and stops comes with US-70
private val SwissRed = Color(0xFFD7192D)
private val SwissRedLight = Color(0xFFFF8A8E)

private val Light = lightColorScheme(primary = SwissRed, onPrimary = Color.White, secondary = Color(0xFF2D327D))
private val Dark = darkColorScheme(primary = SwissRedLight, onPrimary = Color(0xFF5F0010), secondary = Color(0xFFB8BCFF))

/** The app's theme, light or dark as the phone. */
@Composable
fun AppTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (dark) Dark else Light, content = content)
}
