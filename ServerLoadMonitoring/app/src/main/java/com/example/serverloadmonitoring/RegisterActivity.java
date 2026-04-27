package com.example.serverloadmonitoring;

import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONObject;

public class RegisterActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_register);

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });

        MaterialButton registerButton = findViewById(R.id.buttonRegister);
        TextView loginLink = findViewById(R.id.textGoToLogin);
        TextInputEditText nicknameInput = findViewById(R.id.inputRegisterNickname);
        TextInputEditText emailInput = findViewById(R.id.inputRegisterEmail);
        TextInputEditText passwordInput = findViewById(R.id.inputRegisterPassword);
        TextInputEditText confirmPasswordInput = findViewById(R.id.inputRegisterConfirmPassword);

        registerButton.setOnClickListener(v -> {
            String username = textFrom(nicknameInput).trim();
            String email = textFrom(emailInput).trim();
            String password = textFrom(passwordInput);
            String confirmPassword = textFrom(confirmPasswordInput);

            if (TextUtils.isEmpty(username) || TextUtils.isEmpty(password) || TextUtils.isEmpty(confirmPassword)) {
                Toast.makeText(this, R.string.auth_error_fill_register, Toast.LENGTH_SHORT).show();
                return;
            }
            if (!TextUtils.equals(password, confirmPassword)) {
                Toast.makeText(this, R.string.auth_error_password_mismatch, Toast.LENGTH_SHORT).show();
                return;
            }

            registerButton.setEnabled(false);
            try {
                JSONObject payload = new JSONObject();
                payload.put("username", username);
                payload.put("email", email);
                payload.put("password", password);

                ApiClient.post(this, "/api/auth/register/", payload, false, new ApiClient.ResponseCallback() {
                    @Override
                    public void onSuccess(int statusCode, String responseBody) {
                        registerButton.setEnabled(true);
                        try {
                            JSONObject response = new JSONObject(responseBody);
                            ApiSession.saveAuthPayload(RegisterActivity.this, response);
                            NotificationTokenManager.registerKnownTokenIfLoggedIn(RegisterActivity.this);
                            NotificationTokenManager.syncTokenIfPossible(RegisterActivity.this);

                            Intent intent = new Intent(RegisterActivity.this, ServersActivity.class);
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                            startActivity(intent);
                        } catch (Exception exception) {
                            Toast.makeText(
                                RegisterActivity.this,
                                R.string.auth_error_invalid_server_response,
                                Toast.LENGTH_SHORT
                            ).show();
                        }
                    }

                    @Override
                    public void onError(int statusCode, String message, String responseBody) {
                        registerButton.setEnabled(true);
                        Toast.makeText(RegisterActivity.this, message, Toast.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception exception) {
                registerButton.setEnabled(true);
                Toast.makeText(this, R.string.auth_error_unexpected, Toast.LENGTH_SHORT).show();
            }
        });

        loginLink.setOnClickListener(v -> finish());
    }

    private String textFrom(TextInputEditText input) {
        return input.getText() == null ? "" : input.getText().toString();
    }
}
