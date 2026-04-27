package com.example.serverloadmonitoring;

import android.content.Intent;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import org.json.JSONObject;

import java.util.LinkedHashMap;
import java.util.Map;

public class GlobalSettingsActivity extends AppCompatActivity {
    private View panelView;
    private boolean isClosing;
    private boolean isBindingRefreshValue;

    private final LinkedHashMap<String, Integer> refreshLabelToSeconds = new LinkedHashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_global_settings);

        if (!ApiSession.isLoggedIn(this)) {
            openLoginAndFinish();
            return;
        }

        View rootView = findViewById(R.id.globalSettingsRoot);
        panelView = findViewById(R.id.globalSettingsPanel);

        // Hide panel immediately to prevent glitching before animation
        panelView.setAlpha(0f);
        panelView.setTranslationX(-dpToPx(400));
        rootView.setAlpha(0f);

        ViewCompat.setOnApplyWindowInsetsListener(rootView, (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });

        setPanelToHalfScreenWidth();
        animatePanelIn();
        bindProfile();
        setupRefreshOptions();

        rootView.setOnClickListener(v -> closeWithAnimation());
        panelView.setOnClickListener(v -> {
            // consume click inside panel
        });

        TextView logout = findViewById(R.id.itemGlobalLogout);
        logout.setOnClickListener(v -> NotificationTokenManager.unregisterCurrentToken(this, () -> {
            ApiSession.clear(this);
            Toast.makeText(this, R.string.global_settings_logged_out, Toast.LENGTH_SHORT).show();
            openLoginAndFinish();
        }));
    }

    @Override
    public void finish() {
        if (!isClosing) {
            closeWithAnimation();
            return;
        }
        super.finish();
        overridePendingTransition(0, 0);
    }

    @Override
    public void onBackPressed() {
        closeWithAnimation();
    }

    private void bindProfile() {
        TextView nicknameView = findViewById(R.id.textGlobalNickname);
        TextView emailView = findViewById(R.id.textGlobalEmail);

        nicknameView.setText(ApiSession.getUsername(this));
        String email = ApiSession.getEmail(this);
        emailView.setText((email == null || email.trim().isEmpty()) ? "-" : email);
    }

    private void setPanelToHalfScreenWidth() {
        if (panelView == null) {
            return;
        }
        int screenWidth = getResources().getDisplayMetrics().widthPixels;
        int desiredWidth = Math.max((int) (screenWidth * 0.62f), dpToPx(260));
        desiredWidth = Math.min(desiredWidth, dpToPx(360));

        ViewGroup.LayoutParams params = panelView.getLayoutParams();
        params.width = desiredWidth;
        panelView.setLayoutParams(params);
    }

    private void animatePanelIn() {
        if (panelView == null) {
            return;
        }

        View rootView = findViewById(R.id.globalSettingsRoot);
        if (rootView != null) {
            rootView.animate().alpha(1f).setDuration(250).start();
        }

        panelView.post(() -> {
            panelView.setTranslationX(-panelView.getWidth());
            panelView.setAlpha(1f);
            panelView.animate()
                .translationX(0f)
                .setDuration(220)
                .start();
        });
    }

    private void closeWithAnimation() {
        if (panelView == null || isClosing) {
            return;
        }
        isClosing = true;

        View rootView = findViewById(R.id.globalSettingsRoot);
        if (rootView != null) {
            rootView.animate().alpha(0f).setDuration(200).start();
        }

        panelView.animate()
            .translationX(-panelView.getWidth())
            .setDuration(180)
            .withEndAction(() -> {
                super.finish();
                overridePendingTransition(0, 0);
            })
            .start();
    }

    private int dpToPx(int dp) {
        return (int) TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP,
            dp,
            getResources().getDisplayMetrics()
        );
    }

    private void setupRefreshOptions() {
        AutoCompleteTextView inputGlobalRefreshInterval = findViewById(R.id.inputGlobalRefreshInterval);
        if (inputGlobalRefreshInterval == null) {
            return;
        }

        refreshLabelToSeconds.clear();
        refreshLabelToSeconds.put(getString(R.string.global_settings_refresh_interval_2s), 2);
        refreshLabelToSeconds.put(getString(R.string.global_settings_refresh_interval_5s), 5);
        refreshLabelToSeconds.put(getString(R.string.global_settings_refresh_interval_15s), 15);
        refreshLabelToSeconds.put(getString(R.string.global_settings_refresh_interval_30s), 30);
        refreshLabelToSeconds.put(getString(R.string.global_settings_refresh_interval_60s), 60);

        String[] options = refreshLabelToSeconds.keySet().toArray(new String[0]);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, options);
        inputGlobalRefreshInterval.setAdapter(adapter);

        int currentSeconds = ApiSession.getDataRefreshIntervalSeconds(this);
        String currentLabel = findLabelForSeconds(currentSeconds);

        isBindingRefreshValue = true;
        inputGlobalRefreshInterval.setText(currentLabel, false);
        isBindingRefreshValue = false;

        inputGlobalRefreshInterval.setOnItemClickListener((parent, view, position, id) -> {
            String selectedLabel = adapter.getItem(position);
            if (selectedLabel == null || isBindingRefreshValue) {
                return;
            }

            Integer seconds = refreshLabelToSeconds.get(selectedLabel);
            if (seconds == null) {
                return;
            }
            saveRefreshInterval(seconds);
        });

        ApiClient.get(this, "/api/users/settings/", true, new ApiClient.ResponseCallback() {
            @Override
            public void onSuccess(int statusCode, String responseBody) {
                try {
                    JSONObject payload = new JSONObject(responseBody);
                    int seconds = payload.optInt("data_refresh_interval_seconds", 5);
                    ApiSession.setDataRefreshIntervalSeconds(GlobalSettingsActivity.this, seconds);
                    String label = findLabelForSeconds(seconds);

                    isBindingRefreshValue = true;
                    inputGlobalRefreshInterval.setText(label, false);
                    isBindingRefreshValue = false;
                } catch (Exception ignored) {
                    // no-op
                }
            }

            @Override
            public void onError(int statusCode, String message, String responseBody) {
                if (statusCode == 401) {
                    ApiSession.clear(GlobalSettingsActivity.this);
                    openLoginAndFinish();
                }
            }
        });
    }

    private String findLabelForSeconds(int seconds) {
        for (Map.Entry<String, Integer> entry : refreshLabelToSeconds.entrySet()) {
            if (entry.getValue() == seconds) {
                return entry.getKey();
            }
        }
        return getString(R.string.global_settings_refresh_interval_5s);
    }

    private void saveRefreshInterval(int seconds) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("data_refresh_interval_seconds", seconds);

            ApiClient.patch(this, "/api/users/settings/", payload, true, new ApiClient.ResponseCallback() {
                @Override
                public void onSuccess(int statusCode, String responseBody) {
                    ApiSession.setDataRefreshIntervalSeconds(GlobalSettingsActivity.this, seconds);
                    Toast.makeText(GlobalSettingsActivity.this, R.string.global_settings_saved, Toast.LENGTH_SHORT).show();
                }

                @Override
                public void onError(int statusCode, String message, String responseBody) {
                    if (statusCode == 401) {
                        ApiSession.clear(GlobalSettingsActivity.this);
                        openLoginAndFinish();
                        return;
                    }
                    Toast.makeText(GlobalSettingsActivity.this, message, Toast.LENGTH_SHORT).show();
                }
            });
        } catch (Exception exception) {
            Toast.makeText(this, R.string.auth_error_unexpected, Toast.LENGTH_SHORT).show();
        }
    }

    private void openLoginAndFinish() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
        super.finish();
        overridePendingTransition(0, 0);
    }
}
