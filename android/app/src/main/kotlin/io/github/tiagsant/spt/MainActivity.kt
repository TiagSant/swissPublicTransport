package io.github.tiagsant.spt

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import io.github.tiagsant.spt.ui.AppTheme
import io.github.tiagsant.spt.ui.SwissPublicTransportApp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            AppTheme {
                SwissPublicTransportApp()
            }
        }
    }
}
