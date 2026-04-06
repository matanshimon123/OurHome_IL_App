package com.ourhome.il;

import android.animation.AnimatorSet;
import android.animation.ObjectAnimator;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.ViewGroup;
import android.view.animation.AccelerateDecelerateInterpolator;
import android.webkit.JavascriptInterface;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import com.getcapacitor.BridgeActivity;
import com.google.firebase.messaging.FirebaseMessaging;

public class MainActivity extends BridgeActivity {

    private static final int BLUE_DARK  = Color.parseColor("#1d4ed8");
    private static final int BLUE_MID   = Color.parseColor("#2563eb");
    private static final int BLUE_LIGHT = Color.parseColor("#3b82f6");
    private static final int TIMEOUT_MS = 10000; // 10 שניות timeout

    private String fcmToken = null;
    private FrameLayout splashOverlay = null;
    private TextView statusText = null;
    private ProgressBar spinner = null;
    private Button retryBtn = null;
    private Handler handler = new Handler(Looper.getMainLooper());
    private boolean pageSignaled = false; // JS יאמר לנו שהדף נטען

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        getWindow().setBackgroundDrawable(
                new android.graphics.drawable.ColorDrawable(BLUE_MID)
        );
        super.onCreate(savedInstanceState);
        getBridge().getWebView().setBackgroundColor(BLUE_MID);

        // Interfaces
        getBridge().getWebView().addJavascriptInterface(new ShareInterface(), "AndroidShare");
        getBridge().getWebView().addJavascriptInterface(new FcmInterface(), "AndroidFCM");
        getBridge().getWebView().addJavascriptInterface(new PageReadyInterface(), "AndroidPageReady");

        showSplash();

        if (!isConnected()) {
            showNoNetwork();
        } else {
            startLoadingFlow();
        }

        // FCM
        FirebaseMessaging.getInstance().getToken()
                .addOnCompleteListener(task -> {
                    if (task.isSuccessful() && task.getResult() != null)
                        fcmToken = task.getResult();
                });
    }

    // ── JS קורא לזה כשהדף נטען בהצלחה ──────────────────────
    class PageReadyInterface {
        @JavascriptInterface
        public void onReady() {
            pageSignaled = true;
            handler.removeCallbacksAndMessages(null);
            hideSplash();
        }
    }

    // ── Timeout – אם JS לא ענה תוך 10 שניות ──────────────────
    private void startLoadingFlow() {
        // סטטוס מתחלף
        String[] msgs = {"מתחבר לשרת...", "טוען נתונים...", "מכין את הממשק..."};
        for (int i = 0; i < msgs.length; i++) {
            final String msg = msgs[i];
            handler.postDelayed(() -> {
                if (!pageSignaled && statusText != null)
                    statusText.setText(msg);
            }, i * 3000L);
        }

        // Timeout אחרי 10 שניות
        handler.postDelayed(() -> {
            if (!pageSignaled) {
                if (isConnected()) showServerError();
                else showNoNetwork();
            }
        }, TIMEOUT_MS);
    }

    // ── Splash UI ────────────────────────────────────────────
    private void showSplash() {
        splashOverlay = new FrameLayout(this);
        splashOverlay.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        GradientDrawable bg = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                new int[]{BLUE_DARK, BLUE_MID, BLUE_LIGHT});
        splashOverlay.setBackground(bg);

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(Gravity.CENTER);
        content.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        content.setPadding(80, 0, 80, 120);

        // לוגו
        TextView logo = new TextView(this);
        logo.setText("🏠");
        logo.setTextSize(64);
        logo.setGravity(Gravity.CENTER);
        logo.setPadding(0, 0, 0, 16);
        content.addView(logo);

        // כותרת
        TextView title = new TextView(this);
        title.setText("OurHome IL");
        title.setTextColor(Color.WHITE);
        title.setTextSize(28);
        title.setTypeface(null, Typeface.BOLD);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 0, 0, 8);
        content.addView(title);

        // תת-כותרת
        TextView subtitle = new TextView(this);
        subtitle.setText("ניהול משפחתי חכם");
        subtitle.setTextColor(Color.argb(180, 255, 255, 255));
        subtitle.setTextSize(14);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setPadding(0, 0, 0, 60);
        content.addView(subtitle);

        // Spinner
        spinner = new ProgressBar(this, null, android.R.attr.progressBarStyleLarge);
        spinner.getIndeterminateDrawable().setColorFilter(
                Color.WHITE, android.graphics.PorterDuff.Mode.SRC_IN);
        LinearLayout.LayoutParams spinnerParams = new LinearLayout.LayoutParams(80, 80);
        spinnerParams.gravity = Gravity.CENTER_HORIZONTAL;
        spinnerParams.bottomMargin = 24;
        spinner.setLayoutParams(spinnerParams);
        content.addView(spinner);

        // סטטוס
        statusText = new TextView(this);
        statusText.setText("מתחבר לשרת...");
        statusText.setTextColor(Color.argb(200, 255, 255, 255));
        statusText.setTextSize(13);
        statusText.setGravity(Gravity.CENTER);
        statusText.setPadding(0, 0, 0, 32);
        content.addView(statusText);

        // כפתור נסה שוב
        retryBtn = new Button(this);
        retryBtn.setText("נסה שוב");
        retryBtn.setTextColor(Color.WHITE);
        retryBtn.setTextSize(15);
        retryBtn.setTypeface(null, Typeface.BOLD);
        GradientDrawable btnBg = new GradientDrawable();
        btnBg.setColor(Color.argb(60, 255, 255, 255));
        btnBg.setStroke(2, Color.argb(150, 255, 255, 255));
        btnBg.setCornerRadius(50);
        retryBtn.setBackground(btnBg);
        LinearLayout.LayoutParams btnParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        btnParams.gravity = Gravity.CENTER_HORIZONTAL;
        retryBtn.setLayoutParams(btnParams);
        retryBtn.setPadding(80, 28, 80, 28);
        retryBtn.setVisibility(android.view.View.GONE);
        retryBtn.setOnClickListener(v -> retry());
        content.addView(retryBtn);

        splashOverlay.addView(content);

        splashOverlay.setAlpha(0f);
        ViewGroup root = (ViewGroup) getWindow().getDecorView().getRootView();
        root.addView(splashOverlay);
        splashOverlay.animate().alpha(1f).setDuration(300).start();

        // אנימציית pulse ללוגו
        pulseLogo(logo);
    }

    private void pulseLogo(TextView logo) {
        ObjectAnimator sx = ObjectAnimator.ofFloat(logo, "scaleX", 1f, 1.1f, 1f);
        ObjectAnimator sy = ObjectAnimator.ofFloat(logo, "scaleY", 1f, 1.1f, 1f);
        AnimatorSet pulse = new AnimatorSet();
        pulse.playTogether(sx, sy);
        pulse.setDuration(1600);
        pulse.setInterpolator(new AccelerateDecelerateInterpolator());
        pulse.start();
        handler.postDelayed(() -> { if (splashOverlay != null) pulseLogo(logo); }, 500);
    }

    private void showNoNetwork() {
        runOnUiThread(() -> {
            if (splashOverlay == null) return;
            spinner.setVisibility(android.view.View.GONE);
            statusText.setText("אין חיבור לאינטרנט\nבדוק WiFi או דאטה ונסה שוב");
            statusText.setTextSize(14);
            retryBtn.setVisibility(android.view.View.VISIBLE);
        });
    }

    private void showServerError() {
        runOnUiThread(() -> {
            if (splashOverlay == null) return;
            spinner.setVisibility(android.view.View.GONE);
            statusText.setText("השרת אינו זמין כרגע\nנסה שוב מאוחר יותר");
            statusText.setTextSize(14);
            retryBtn.setVisibility(android.view.View.VISIBLE);
        });
    }

    private void retry() {
        if (!isConnected()) {
            android.widget.Toast.makeText(this,
                    "עדיין אין חיבור אינטרנט", android.widget.Toast.LENGTH_SHORT).show();
            return;
        }
        pageSignaled = false;
        retryBtn.setVisibility(android.view.View.GONE);
        spinner.setVisibility(android.view.View.VISIBLE);
        statusText.setText("מתחבר מחדש...");
        getBridge().reload();
        startLoadingFlow();
    }

    private void hideSplash() {
        runOnUiThread(() -> {
            if (splashOverlay == null) return;
            splashOverlay.animate()
                    .alpha(0f).setDuration(400)
                    .withEndAction(() -> {
                        ViewGroup root = (ViewGroup) getWindow().getDecorView().getRootView();
                        root.removeView(splashOverlay);
                        splashOverlay = null;
                        handler.removeCallbacksAndMessages(null);
                    }).start();
        });
    }

    @Override
    public void onResume() {
        super.onResume();
        if (splashOverlay != null && isConnected() &&
                spinner != null && spinner.getVisibility() == android.view.View.GONE) {
            retry();
        }
    }

    private boolean isConnected() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        if (cm == null) return false;
        NetworkInfo info = cm.getActiveNetworkInfo();
        return info != null && info.isConnected();
    }

    @Override
    public void onBackPressed() {
        if (splashOverlay != null) { finish(); return; }
        if (getBridge().getWebView().canGoBack()) getBridge().getWebView().goBack();
        else super.onBackPressed();
    }

    class ShareInterface {
        @JavascriptInterface
        public void share(String text) {
            Intent intent = new Intent(Intent.ACTION_SEND);
            intent.setType("text/plain");
            intent.putExtra(Intent.EXTRA_TEXT, text);
            startActivity(Intent.createChooser(intent, "שתף קוד הזמנה"));
        }
    }

    class FcmInterface {
        @JavascriptInterface
        public String getToken() { return fcmToken != null ? fcmToken : ""; }
    }
}