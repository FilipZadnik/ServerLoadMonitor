package com.example.serverloadmonitoring;

import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.ImageButton;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.switchmaterial.SwitchMaterial;
import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONObject;

public class ServerSettingsActivity extends AppCompatActivity {
    public static final String EXTRA_SERVER_ID = "extra_server_id";
    public static final String EXTRA_SERVER_NAME = "extra_server_name";

    private int serverId;
    private String serverName;

    private TextView title;
    private TextInputEditText inputServerName;
    private TextInputEditText inputMetricInterval;
    private TextInputEditText inputProcessInterval;
    private TextInputEditText inputServiceInterval;
    private TextInputEditText inputRetentionDays;
    private SwitchMaterial switchNotifyOffline;
    private TextInputEditText inputCpuThreshold;
    private TextInputEditText inputRamThreshold;

    private boolean notifyHighCpu = true;
    private boolean notifyHighRam = true;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_server_settings);

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });

        if (!ApiSession.isLoggedIn(this)) {
            openLoginAndFinish();
            return;
        }

        serverId = getIntent().getIntExtra(EXTRA_SERVER_ID, 0);
        serverName = getIntent().getStringExtra(EXTRA_SERVER_NAME);
        if (serverName == null || serverName.trim().isEmpty()) {
            serverName = getString(R.string.detail_default_server_name);
        }

        if (serverId <= 0) {
            Toast.makeText(this, R.string.server_settings_missing_server, Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        ImageButton backButton = findViewById(R.id.buttonBackServerSettings);
        title = findViewById(R.id.textServerSettingsTitle);
        inputServerName = findViewById(R.id.inputServerSettingsName);
        inputMetricInterval = findViewById(R.id.inputServerSettingsMetricInterval);
        inputProcessInterval = findViewById(R.id.inputServerSettingsProcessInterval);
        inputServiceInterval = findViewById(R.id.inputServerSettingsServiceInterval);
        inputRetentionDays = findViewById(R.id.inputServerSettingsRetentionDays);
        switchNotifyOffline = findViewById(R.id.switchServerSettingsNotifyOffline);
        inputCpuThreshold = findViewById(R.id.inputServerSettingsCpuThreshold);
        inputRamThreshold = findViewById(R.id.inputServerSettingsRamThreshold);

        MaterialButton saveButton = findViewById(R.id.buttonSaveServerSettings);
        MaterialButton deleteButton = findViewById(R.id.buttonDeleteServer);

        title.setText(getString(R.string.server_settings_title_template, serverName));
        inputServerName.setText(serverName);

        backButton.setOnClickListener(v -> finish());
        saveButton.setOnClickListener(v -> saveServerSettings(saveButton));
        deleteButton.setOnClickListener(v -> deleteServer(deleteButton));

        loadServerSettings();
    }

    private void loadServerSettings() {
        ApiClient.get(this, "/api/servers/" + serverId + "/settings/", true, new ApiClient.ResponseCallback() {
            @Override
            public void onSuccess(int statusCode, String responseBody) {
                try {
                    JSONObject payload = new JSONObject(responseBody);

                    String resolvedName = payload.optString("name", serverName);
                    if (!TextUtils.isEmpty(resolvedName)) {
                        serverName = resolvedName;
                    }

                    title.setText(getString(R.string.server_settings_title_template, serverName));
                    inputServerName.setText(serverName);
                    inputMetricInterval.setText(String.valueOf(payload.optInt("interval_seconds", 5)));
                    inputProcessInterval.setText(String.valueOf(payload.optInt("process_snapshot_interval_seconds", 30)));
                    inputServiceInterval.setText(String.valueOf(payload.optInt("service_snapshot_interval_seconds", 60)));
                    inputRetentionDays.setText(String.valueOf(payload.optInt("metric_retention_days", 30)));
                    switchNotifyOffline.setChecked(payload.optBoolean("notify_on_offline", true));

                    notifyHighCpu = payload.optBoolean("notify_on_high_cpu", true);
                    notifyHighRam = payload.optBoolean("notify_on_high_ram", true);
                    inputCpuThreshold.setText(String.valueOf(payload.optInt("cpu_alert_threshold_percent", 85)));
                    inputRamThreshold.setText(String.valueOf(payload.optInt("ram_alert_threshold_percent", 90)));
                } catch (Exception exception) {
                    Toast.makeText(ServerSettingsActivity.this, R.string.server_settings_parse_error, Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onError(int statusCode, String message, String responseBody) {
                if (statusCode == 401) {
                    ApiSession.clear(ServerSettingsActivity.this);
                    openLoginAndFinish();
                    return;
                }
                Toast.makeText(ServerSettingsActivity.this, message, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void saveServerSettings(MaterialButton saveButton) {
        String resolvedDisplayName = textFrom(inputServerName).trim();
        if (TextUtils.isEmpty(resolvedDisplayName)) {
            resolvedDisplayName = serverName;
        }
        final String displayName = resolvedDisplayName;

        int metricInterval = ServerPreferences.parsePositiveOrDefault(textFrom(inputMetricInterval), 5, 1, 3600);
        int processInterval = ServerPreferences.parsePositiveOrDefault(textFrom(inputProcessInterval), 30, 1, 3600);
        int serviceInterval = ServerPreferences.parsePositiveOrDefault(textFrom(inputServiceInterval), 60, 1, 3600);
        int retentionDays = ServerPreferences.parsePositiveOrDefault(textFrom(inputRetentionDays), 30, 1, 3650);
        int cpuThreshold = ServerPreferences.parsePositiveOrDefault(textFrom(inputCpuThreshold), 85, 1, 100);
        int ramThreshold = ServerPreferences.parsePositiveOrDefault(textFrom(inputRamThreshold), 90, 1, 100);

        saveButton.setEnabled(false);
        try {
            JSONObject payload = new JSONObject();
            payload.put("name", displayName);
            payload.put("interval_seconds", metricInterval);
            payload.put("process_snapshot_interval_seconds", processInterval);
            payload.put("service_snapshot_interval_seconds", serviceInterval);
            payload.put("metric_retention_days", retentionDays);
            payload.put("notify_on_offline", switchNotifyOffline.isChecked());
            payload.put("notify_on_high_cpu", notifyHighCpu);
            payload.put("notify_on_high_ram", notifyHighRam);
            payload.put("cpu_alert_threshold_percent", cpuThreshold);
            payload.put("ram_alert_threshold_percent", ramThreshold);

            ApiClient.patch(this, "/api/servers/" + serverId + "/settings/", payload, true, new ApiClient.ResponseCallback() {
                @Override
                public void onSuccess(int statusCode, String responseBody) {
                    saveButton.setEnabled(true);
                    serverName = displayName;
                    title.setText(getString(R.string.server_settings_title_template, serverName));
                    Toast.makeText(ServerSettingsActivity.this, R.string.server_settings_saved_toast, Toast.LENGTH_SHORT).show();
                }

                @Override
                public void onError(int statusCode, String message, String responseBody) {
                    saveButton.setEnabled(true);
                    if (statusCode == 401) {
                        ApiSession.clear(ServerSettingsActivity.this);
                        openLoginAndFinish();
                        return;
                    }
                    Toast.makeText(ServerSettingsActivity.this, message, Toast.LENGTH_SHORT).show();
                }
            });
        } catch (Exception exception) {
            saveButton.setEnabled(true);
            Toast.makeText(this, R.string.auth_error_unexpected, Toast.LENGTH_SHORT).show();
        }
    }

    private void deleteServer(MaterialButton deleteButton) {
        deleteButton.setEnabled(false);
        ApiClient.delete(this, "/api/servers/" + serverId + "/settings/", true, new ApiClient.ResponseCallback() {
            @Override
            public void onSuccess(int statusCode, String responseBody) {
                deleteButton.setEnabled(true);
                Toast.makeText(ServerSettingsActivity.this, R.string.server_settings_deleted, Toast.LENGTH_SHORT).show();
                openServersAfterDelete();
            }

            @Override
            public void onError(int statusCode, String message, String responseBody) {
                deleteButton.setEnabled(true);
                if (statusCode == 401) {
                    ApiSession.clear(ServerSettingsActivity.this);
                    openLoginAndFinish();
                    return;
                }
                Toast.makeText(ServerSettingsActivity.this, message, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private String textFrom(TextInputEditText input) {
        return input.getText() == null ? "" : input.getText().toString();
    }

    private void openLoginAndFinish() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
        finish();
    }

    private void openServersAfterDelete() {
        Intent intent = new Intent(this, ServersActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
        finish();
    }
}
