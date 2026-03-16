package com.whim.recorder;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends Activity {

    private static final String SERVER_URL = "http://100.69.17.20:8089";
    private static final int CONNECT_TIMEOUT = 4000;
    private static final int READ_TIMEOUT = 4000;
    private static final int MAX_RETRIES = 5;
    private static final int MIC_PERMISSION_CODE = 1001;
    private static final int SPEECH_REQUEST_CODE = 1002;

    private WebView webView;

    private static final String LOADING_HTML =
        "<html><body style=\"background:#1e1e1e;color:#dce4ee;font-family:sans-serif;" +
        "display:flex;flex-direction:column;align-items:center;justify-content:center;" +
        "height:100vh;text-align:center\">" +
        "<svg viewBox=\"0 0 64 64\" width=\"96\" height=\"96\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">" +
        "<circle cx=\"32\" cy=\"32\" r=\"30\" stroke=\"#00ff00\" stroke-width=\"2\" fill=\"none\"/>" +
        "<path d=\"M16 32 Q20 18,24 32 Q28 46,32 32 Q36 18,40 32 Q44 46,48 32\" " +
        "stroke=\"#00ff00\" stroke-width=\"2.5\" fill=\"none\" stroke-linecap=\"round\"/></svg>" +
        "<p style=\"color:#00ff00;margin-top:24px;font-size:24px;font-family:Courier New,monospace\">" +
        "Connecting to Whim...</p>" +
        "<p style=\"color:#555;font-size:16px;margin-top:12px\">" + SERVER_URL + "</p>" +
        "</body></html>";

    private static final String ERROR_HTML =
        "<html><body style=\"background:#1e1e1e;color:#dce4ee;font-family:sans-serif;" +
        "display:flex;flex-direction:column;align-items:center;justify-content:center;" +
        "height:100vh;text-align:center;padding:24px\">" +
        "<svg viewBox=\"0 0 64 64\" width=\"96\" height=\"96\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">" +
        "<circle cx=\"32\" cy=\"32\" r=\"30\" stroke=\"#d94040\" stroke-width=\"2\" fill=\"none\"/>" +
        "<path d=\"M16 32 Q20 18,24 32 Q28 46,32 32 Q36 18,40 32 Q44 46,48 32\" " +
        "stroke=\"#d94040\" stroke-width=\"2.5\" fill=\"none\" stroke-linecap=\"round\"/></svg>" +
        "<h2 style=\"color:#d94040;margin-top:24px;font-size:28px\">Cannot reach Whim</h2>" +
        "<p style=\"color:#888;font-size:18px;margin-top:12px\">Make sure Whim is running on your PC and Tailscale is connected.</p>" +
        "<p style=\"color:#555;font-size:16px;margin-top:8px\">" + SERVER_URL + "</p>" +
        "<button onclick=\"WhimBridge.retry()\" style=\"margin-top:32px;padding:24px 60px;" +
        "background:#2fa572;color:#fff;border:none;border-radius:16px;font-size:24px;" +
        "cursor:pointer;font-weight:600\">Retry</button></body></html>";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        enterImmersive();

        FrameLayout root = new FrameLayout(this);
        root.setLayoutParams(new ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        root.setBackgroundColor(Color.parseColor("#1e1e1e"));

        webView = new WebView(this);
        webView.setLayoutParams(new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        webView.setBackgroundColor(Color.parseColor("#1e1e1e"));

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setAllowFileAccess(true);
        ws.setAllowFileAccessFromFileURLs(true);
        ws.setAllowUniversalAccessFromFileURLs(true);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        ws.setUseWideViewPort(true);
        ws.setLoadWithOverviewMode(true);

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        request.grant(request.getResources());
                    }
                });
            }
        });

        webView.setWebViewClient(new WebViewClient());
        webView.addJavascriptInterface(new WhimBridge(), "WhimBridge");

        root.addView(webView);
        setContentView(root);

        String[] neededPerms = {"android.permission.RECORD_AUDIO", "android.permission.CAMERA"};
        java.util.ArrayList<String> missing = new java.util.ArrayList<>();
        for (String p : neededPerms) {
            if (checkSelfPermission(p) != PackageManager.PERMISSION_GRANTED) missing.add(p);
        }
        if (!missing.isEmpty()) {
            requestPermissions(missing.toArray(new String[0]), MIC_PERMISSION_CODE);
        }

        loadApp();
    }

    private void enterImmersive() {
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.parseColor("#1e1e1e"));
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) enterImmersive();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == MIC_PERMISSION_CODE) {
            loadApp();
        }
    }

    private void loadApp() {
        webView.loadDataWithBaseURL("file:///android_asset/index.html",
            LOADING_HTML, "text/html", "UTF-8", null);
        new Thread(new Runnable() {
            @Override
            public void run() {
                for (int attempt = 0; attempt < MAX_RETRIES; attempt++) {
                    try {
                        URL url = new URL(SERVER_URL);
                        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                        conn.setConnectTimeout(CONNECT_TIMEOUT);
                        conn.setReadTimeout(READ_TIMEOUT);
                        int code = conn.getResponseCode();
                        if (code == 200) {
                            InputStream is = conn.getInputStream();
                            ByteArrayOutputStream bos = new ByteArrayOutputStream();
                            byte[] buf = new byte[4096];
                            int n;
                            while ((n = is.read(buf)) != -1) bos.write(buf, 0, n);
                            is.close();
                            conn.disconnect();
                            String html = bos.toString("UTF-8");
                            html = html.replace("fetch('/", "fetch('" + SERVER_URL + "/");
                            html = html.replace("'POST','/", "'POST','" + SERVER_URL + "/");
                            html = html.replace("'GET','/", "'GET','" + SERVER_URL + "/");
                            final String patched = html;
                            runOnUiThread(new Runnable() {
                                @Override
                                public void run() {
                                    webView.loadDataWithBaseURL(
                                        "file:///android_asset/index.html",
                                        patched, "text/html", "UTF-8", null);
                                }
                            });
                            return;
                        }
                        conn.disconnect();
                    } catch (Exception e) {
                        // retry
                    }
                    try { Thread.sleep(1500); } catch (Exception e) {}
                }
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        showError();
                    }
                });
            }
        }).start();
    }

    private void showError() {
        webView.loadDataWithBaseURL("file:///android_asset/index.html",
            ERROR_HTML, "text/html", "UTF-8", null);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == SPEECH_REQUEST_CODE && resultCode == RESULT_OK && data != null) {
            java.util.ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (results != null && !results.isEmpty()) {
                final String spoken = results.get(0);
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        webView.evaluateJavascript(
                            "document.getElementById('chatInput').value='" +
                            spoken.replace("'", "\\'") + "';sendChat();", null);
                    }
                });
            }
        }
    }

    class WhimBridge {
        @JavascriptInterface
        public void retry() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    loadApp();
                }
            });
        }

        @JavascriptInterface
        public void onWakeWord() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                    intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                    intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US");
                    intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Whim is listening...");
                    try {
                        startActivityForResult(intent, SPEECH_REQUEST_CODE);
                    } catch (Exception e) {
                        // Speech recognizer not available
                    }
                }
            });
        }

        @JavascriptInterface
        public void onReady() {
            // App loaded callback
        }
    }
}
