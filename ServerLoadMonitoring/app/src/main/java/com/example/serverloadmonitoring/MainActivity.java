package com.example.serverloadmonitoring;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONObject;

public class MainActivity extends AppCompatActivity {
    private static final int REQUEST_CODE_POST_NOTIFICATIONS = 101;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_main);

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });

        requestNotificationPermissionIfNeeded();

        if (ApiSession.isLoggedIn(this)) {
            NotificationTokenManager.registerKnownTokenIfLoggedIn(this);
            NotificationTokenManager.syncTokenIfPossible(this);
            openServersAndFinish();
            return;
        }

        MaterialButton loginButton = findViewById(R.id.buttonLogin);
        TextView registerLink = findViewById(R.id.textGoToRegister);
        TextInputEditText nicknameInput = findViewById(R.id.inputNickname);
        TextInputEditText passwordInput = findViewById(R.id.inputPassword);

        loginButton.setOnClickListener(v -> {
            String username = textFrom(nicknameInput).trim();
            String password = textFrom(passwordInput);
            if (TextUtils.isEmpty(username) || TextUtils.isEmpty(password)) {
                Toast.makeText(this, R.string.auth_error_fill_credentials, Toast.LENGTH_SHORT).show();
                return;
            }

            loginButton.setEnabled(false);
            try {
                JSONObject payload = new JSONObject();
                payload.put("username", username);
                payload.put("password", password);

                ApiClient.post(this, "/api/auth/login/", payload, false, new ApiClient.ResponseCallback() {
                    @Override
                    public void onSuccess(int statusCode, String responseBody) {
                        loginButton.setEnabled(true);
                        try {
                            JSONObject response = new JSONObject(responseBody);
                            ApiSession.saveAuthPayload(MainActivity.this, response);
                            NotificationTokenManager.registerKnownTokenIfLoggedIn(MainActivity.this);
                            NotificationTokenManager.syncTokenIfPossible(MainActivity.this);
                            openServersAndFinish();
                        } catch (Exception exception) {
                            Toast.makeText(
                                MainActivity.this,
                                R.string.auth_error_invalid_server_response,
                                Toast.LENGTH_SHORT
                            ).show();
                        }
                    }

                    @Override
                    public void onError(int statusCode, String message, String responseBody) {
                        loginButton.setEnabled(true);
                        Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception exception) {
                loginButton.setEnabled(true);
                Toast.makeText(this, R.string.auth_error_unexpected, Toast.LENGTH_SHORT).show();
            }
        });

        registerLink.setOnClickListener(v -> {
            Intent intent = new Intent(MainActivity.this, RegisterActivity.class);
            startActivity(intent);
        });
    }

    private String textFrom(TextInputEditText input) {
        return input.getText() == null ? "" : input.getText().toString();
    }

    private void openServersAndFinish() {
        Intent intent = new Intent(MainActivity.this, ServersActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            == PackageManager.PERMISSION_GRANTED) {
            return;
        }

        ActivityCompat.requestPermissions(
            this,
            new String[]{Manifest.permission.POST_NOTIFICATIONS},
            REQUEST_CODE_POST_NOTIFICATIONS
        );
    }
}
