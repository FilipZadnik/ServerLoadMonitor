package com.example.serverloadmonitoring;

import android.content.Intent;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextUtils;
import android.text.TextWatcher;
import android.widget.ImageButton;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.activity.result.ActivityResultLauncher;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.google.android.material.textfield.TextInputEditText;
import com.journeyapps.barcodescanner.ScanContract;
import com.journeyapps.barcodescanner.ScanOptions;

import org.json.JSONObject;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class AddServerActivity extends AppCompatActivity {
    private static final Pattern PAIRING_CODE_PATTERN = Pattern.compile("\\b\\d{3}-\\d{3}\\b");

    private boolean isFormattingPairingCode;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_add_server);

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });

        if (!ApiSession.isLoggedIn(this)) {
            openLoginAndFinish();
            return;
        }

        ImageButton backButton = findViewById(R.id.buttonBack);
        MaterialButton guideButton = findViewById(R.id.buttonAgentGuide);
        MaterialButton scanButton = findViewById(R.id.buttonScanQrCode);
        MaterialButton saveButton = findViewById(R.id.buttonPairServer);

        TextInputEditText nameInput = findViewById(R.id.inputServerName);
        TextInputEditText pairingCodeInput = findViewById(R.id.inputPairingCode);
        TextInputEditText metricIntervalInput = findViewById(R.id.inputMetricInterval);
        TextInputEditText processIntervalInput = findViewById(R.id.inputProcessInterval);
        TextInputEditText serviceIntervalInput = findViewById(R.id.inputServiceInterval);

        setupPairingCodeAutoFormatting(pairingCodeInput);

        ActivityResultLauncher<ScanOptions> qrScannerLauncher = registerForActivityResult(
            new ScanContract(),
            result -> {
                String content = result != null ? result.getContents() : null;
                if (TextUtils.isEmpty(content)) {
                    return;
                }

                Matcher matcher = PAIRING_CODE_PATTERN.matcher(content);
                if (matcher.find()) {
                    pairingCodeInput.setText(matcher.group());
                    Toast.makeText(this, R.string.add_server_scan_success, Toast.LENGTH_SHORT).show();
                } else {
                    Toast.makeText(this, R.string.add_server_scan_invalid, Toast.LENGTH_SHORT).show();
                }
            }
        );

        backButton.setOnClickListener(v -> finish());

        guideButton.setOnClickListener(v -> new MaterialAlertDialogBuilder(this)
            .setTitle(R.string.add_server_guide_title)
            .setMessage(R.string.add_server_guide_message)
            .setPositiveButton(R.string.add_server_guide_close, (dialog, which) -> dialog.dismiss())
            .show());

        scanButton.setOnClickListener(v -> {
            ScanOptions options = new ScanOptions();
            options.setDesiredBarcodeFormats(ScanOptions.QR_CODE);
            options.setPrompt(getString(R.string.add_server_scan_prompt));
            options.setBeepEnabled(false);
            options.setOrientationLocked(true);
            qrScannerLauncher.launch(options);
        });

        saveButton.setOnClickListener(v -> {
            String serverName = textFrom(nameInput).trim();
            String pairingCode = formatPairingCode(textFrom(pairingCodeInput));

            if (TextUtils.isEmpty(serverName)) {
                Toast.makeText(this, R.string.add_server_required_name, Toast.LENGTH_SHORT).show();
                return;
            }
            if (!PAIRING_CODE_PATTERN.matcher(pairingCode).matches()) {
                Toast.makeText(this, R.string.add_server_required_pairing, Toast.LENGTH_SHORT).show();
                return;
            }

            int metricInterval = ServerPreferences.parsePositiveOrDefault(textFrom(metricIntervalInput), 5, 1, 3600);
            int processInterval = ServerPreferences.parsePositiveOrDefault(textFrom(processIntervalInput), 30, 1, 3600);
            int serviceInterval = ServerPreferences.parsePositiveOrDefault(textFrom(serviceIntervalInput), 60, 1, 3600);

            saveButton.setEnabled(false);
            try {
                JSONObject payload = new JSONObject();
                payload.put("name", serverName);
                payload.put("pairing_code", pairingCode);
                payload.put("interval_seconds", metricInterval);
                payload.put("process_snapshot_interval_seconds", processInterval);
                payload.put("service_snapshot_interval_seconds", serviceInterval);

                ApiClient.post(this, "/api/servers/pair/", payload, true, new ApiClient.ResponseCallback() {
                    @Override
                    public void onSuccess(int statusCode, String responseBody) {
                        saveButton.setEnabled(true);
                        try {
                            JSONObject response = new JSONObject(responseBody);
                            int serverId = response.optInt("id", 0);
                            String resolvedName = response.optString("name", serverName);

                            Toast.makeText(AddServerActivity.this, R.string.add_server_paired_success, Toast.LENGTH_SHORT).show();
                            Intent intent = new Intent(AddServerActivity.this, ServerDetailActivity.class);
                            intent.putExtra(ServerDetailActivity.EXTRA_SERVER_ID, serverId);
                            intent.putExtra(ServerDetailActivity.EXTRA_SERVER_NAME, resolvedName);
                            startActivity(intent);
                            finish();
                        } catch (Exception exception) {
                            Toast.makeText(AddServerActivity.this, R.string.add_server_parse_error, Toast.LENGTH_SHORT).show();
                        }
                    }

                    @Override
                    public void onError(int statusCode, String message, String responseBody) {
                        saveButton.setEnabled(true);
                        if (statusCode == 401) {
                            ApiSession.clear(AddServerActivity.this);
                            openLoginAndFinish();
                            return;
                        }
                        Toast.makeText(AddServerActivity.this, message, Toast.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception exception) {
                saveButton.setEnabled(true);
                Toast.makeText(this, R.string.auth_error_unexpected, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void setupPairingCodeAutoFormatting(TextInputEditText pairingCodeInput) {
        pairingCodeInput.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {
                // no-op
            }

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
                // no-op
            }

            @Override
            public void afterTextChanged(Editable s) {
                if (isFormattingPairingCode || s == null) {
                    return;
                }

                String current = s.toString();
                String formatted = formatPairingCode(current);
                if (current.equals(formatted)) {
                    return;
                }

                isFormattingPairingCode = true;
                pairingCodeInput.setText(formatted);
                pairingCodeInput.setSelection(formatted.length());
                isFormattingPairingCode = false;
            }
        });
    }

    private String formatPairingCode(String value) {
        String digitsOnly = value.replaceAll("\\D", "");
        if (digitsOnly.length() > 6) {
            digitsOnly = digitsOnly.substring(0, 6);
        }

        if (digitsOnly.length() <= 3) {
            return digitsOnly;
        }
        return digitsOnly.substring(0, 3) + "-" + digitsOnly.substring(3);
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
}
