package app.blackmarket.botcontrol;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.webkit.HttpAuthHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final int MENU_REFRESH = 1;
    private static final int MENU_SERVER = 2;
    private static final int MENU_LOGOUT = 3;
    private static final String PREFS = "bot_control";
    private static final String URL_KEY = "dashboard_url";
    private static final String PASSWORD_KEY = "dashboard_password";

    private WebView dashboard;
    private ProgressBar progress;
    private SharedPreferences preferences;
    private boolean savedPasswordAttempted;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_main);
        preferences = getSharedPreferences(PREFS, MODE_PRIVATE);
        dashboard = findViewById(R.id.dashboard);
        progress = findViewById(R.id.progress);

        dashboard.getSettings().setJavaScriptEnabled(true);
        dashboard.getSettings().setDomStorageEnabled(true);
        dashboard.getSettings().setBuiltInZoomControls(false);
        dashboard.getSettings().setDisplayZoomControls(false);
        dashboard.getSettings().setUserAgentString(
            dashboard.getSettings().getUserAgentString() + " BotControl/1.0"
        );
        dashboard.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progress.setProgress(newProgress);
                progress.setVisibility(newProgress == 100 ? View.GONE : View.VISIBLE);
            }
        });
        dashboard.setWebViewClient(new DashboardClient());

        if (state == null) {
            dashboard.loadUrl(getDashboardUrl());
        }
    }

    private String getDashboardUrl() {
        return preferences.getString(URL_KEY, getString(R.string.default_dashboard_url));
    }

    private final class DashboardClient extends WebViewClient {
        @Override
        public void onPageStarted(WebView view, String url, Bitmap favicon) {
            progress.setVisibility(View.VISIBLE);
        }

        @Override
        public void onReceivedHttpAuthRequest(
            WebView view,
            HttpAuthHandler handler,
            String host,
            String realm
        ) {
            String savedPassword = preferences.getString(PASSWORD_KEY, "");
            if (!savedPassword.isEmpty() && !savedPasswordAttempted) {
                savedPasswordAttempted = true;
                handler.proceed("admin", savedPassword);
                return;
            }
            preferences.edit().remove(PASSWORD_KEY).apply();
            promptForPassword(handler, host);
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri target = request.getUrl();
            Uri dashboardUri = Uri.parse(getDashboardUrl());
            if ("https".equals(target.getScheme())
                && target.getHost() != null
                && target.getHost().equalsIgnoreCase(dashboardUri.getHost())) {
                return false;
            }
            if ("http".equals(target.getScheme()) || "https".equals(target.getScheme())
                || "tg".equals(target.getScheme())) {
                startActivity(new Intent(Intent.ACTION_VIEW, target));
                return true;
            }
            return false;
        }

        @Override
        public void onReceivedError(
            WebView view,
            WebResourceRequest request,
            WebResourceError error
        ) {
            if (request.isForMainFrame()) {
                Toast.makeText(
                    MainActivity.this,
                    "Dashboard unavailable. Check your connection and server address.",
                    Toast.LENGTH_LONG
                ).show();
            }
        }
    }

    private void promptForPassword(HttpAuthHandler handler, String host) {
        EditText input = new EditText(this);
        input.setHint("Dashboard password");
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        int padding = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout container = new LinearLayout(this);
        container.setPadding(padding, 0, padding, 0);
        container.addView(input, new LinearLayout.LayoutParams(-1, -2));

        new AlertDialog.Builder(this)
            .setTitle("Sign in to " + host)
            .setView(container)
            .setPositiveButton("Sign in", (dialog, which) -> {
                String password = input.getText().toString();
                if (password.isEmpty()) {
                    handler.cancel();
                    return;
                }
                preferences.edit().putString(PASSWORD_KEY, password).apply();
                handler.proceed("admin", password);
            })
            .setNegativeButton("Cancel", (dialog, which) -> handler.cancel())
            .setOnCancelListener(dialog -> handler.cancel())
            .show();
    }

    @Override
    public void onBackPressed() {
        if (dashboard.canGoBack()) {
            dashboard.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(Menu.NONE, MENU_REFRESH, Menu.NONE, "Refresh")
            .setShowAsAction(MenuItem.SHOW_AS_ACTION_ALWAYS);
        menu.add(Menu.NONE, MENU_SERVER, Menu.NONE, "Server address");
        menu.add(Menu.NONE, MENU_LOGOUT, Menu.NONE, "Forget password");
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == MENU_REFRESH) {
            dashboard.reload();
            return true;
        }
        if (item.getItemId() == MENU_SERVER) {
            promptForServer();
            return true;
        }
        if (item.getItemId() == MENU_LOGOUT) {
            preferences.edit().remove(PASSWORD_KEY).apply();
            savedPasswordAttempted = false;
            dashboard.clearHttpAuthUsernamePassword();
            WebView.clearClientCertPreferences(null);
            dashboard.clearCache(true);
            dashboard.loadUrl(getDashboardUrl());
            Toast.makeText(this, "Saved password removed", Toast.LENGTH_SHORT).show();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void promptForServer() {
        EditText input = new EditText(this);
        input.setText(getDashboardUrl());
        input.setSelectAllOnFocus(true);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        int padding = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout container = new LinearLayout(this);
        container.setPadding(padding, 0, padding, 0);
        container.addView(input, new LinearLayout.LayoutParams(-1, -2));

        new AlertDialog.Builder(this)
            .setTitle("Dashboard address")
            .setMessage("Use an HTTPS address ending in /admin.")
            .setView(container)
            .setPositiveButton("Save", (dialog, which) -> {
                String url = input.getText().toString().trim();
                Uri parsed = Uri.parse(url);
                if (!"https".equals(parsed.getScheme()) || parsed.getHost() == null) {
                    Toast.makeText(this, "A valid HTTPS address is required", Toast.LENGTH_LONG).show();
                    return;
                }
                preferences.edit().putString(URL_KEY, url).remove(PASSWORD_KEY).apply();
                savedPasswordAttempted = false;
                dashboard.clearHttpAuthUsernamePassword();
                dashboard.loadUrl(url);
            })
            .setNegativeButton("Cancel", null)
            .show();
    }

    @Override
    protected void onDestroy() {
        dashboard.destroy();
        super.onDestroy();
    }
}
