package io.github.tiagsant.spt.ui

import androidx.activity.compose.BackHandler
import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import io.github.tiagsant.spt.R

/** The two tabs of the app, as in the prototype. */
enum class Tab(@param:StringRes val title: Int, @param:DrawableRes val icon: Int, @param:StringRes val placeholder: Int) {
    DEPARTURES(R.string.tab_departures, R.drawable.ic_departures, R.string.departures_placeholder),
    JOURNEY(R.string.tab_journey, R.drawable.ic_journey, R.string.journey_placeholder),
}

/** Sprint 10 shell: two tabs and a Settings screen, all placeholders. Screens arrive from Sprint 12. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SwissPublicTransportApp() {
    var tab by rememberSaveable { mutableStateOf(Tab.DEPARTURES) }
    var settings by rememberSaveable { mutableStateOf(false) }

    BackHandler(enabled = settings) { settings = false }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(if (settings) R.string.settings else tab.title)) },
                navigationIcon = {
                    if (settings) {
                        IconButton(onClick = { settings = false }) {
                            Icon(painterResource(R.drawable.ic_back), contentDescription = stringResource(R.string.back))
                        }
                    }
                },
                actions = {
                    if (!settings) {
                        IconButton(onClick = { settings = true }) {
                            Icon(painterResource(R.drawable.ic_settings), contentDescription = stringResource(R.string.settings))
                        }
                    }
                },
            )
        },
        bottomBar = {
            if (!settings) {
                NavigationBar {
                    Tab.entries.forEach { t ->
                        NavigationBarItem(
                            selected = t == tab,
                            onClick = { tab = t },
                            icon = { Icon(painterResource(t.icon), contentDescription = null) },
                            label = { Text(stringResource(t.title)) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        Placeholder(
            stringResource(if (settings) R.string.settings_placeholder else tab.placeholder),
            Modifier.padding(padding),
        )
    }
}

@Composable
private fun Placeholder(text: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Text(text, style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center)
    }
}

@Preview(showBackground = true)
@Composable
private fun AppPreview() {
    AppTheme { SwissPublicTransportApp() }
}
