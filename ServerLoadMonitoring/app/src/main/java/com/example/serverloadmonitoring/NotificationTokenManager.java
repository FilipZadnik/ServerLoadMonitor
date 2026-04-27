package com.example.serverloadmonitoring;

import android.content.Context;
import android.os.Build;
import android.text.TextUtils;

import androidx.annotation.NonNull;

import com.google.firebase.messaging.FirebaseMessaging;

import org.json.JSONObject;

public final class NotificationTokenManager {
    private NotificationTokenManager() {
    }

    public static void syncTokenIfPossible(Context context) {
        Context appContext = context.getApplicationContext();

        FirebaseMessaging.getInstance().getToken().addOnCompleteListener(task -> {
            if (!task.isSuccessful() || task.getResult() == null) {
                return;
            }

            String token = task.getResult().trim();
            handleNewToken(appContext, token);
        });
    }

    public static void handleNewToken(Context context, String rawToken) {
        Context appContext = context.getApplicationContext();
        String token = rawToken == null ? "" : rawToken.trim();
        if (token.isEmpty()) {
            return;
        }

        ApiSession.setFcmToken(appContext, token);
        if (ApiSession.isLoggedIn(appContext)) {
            registerToken(appContext, token);
        }
    }

    public static void registerKnownTokenIfLoggedIn(Context context) {
        Context appContext = context.getApplicationContext();
        if (!ApiSession.isLoggedIn(appContext)) {
            return;
        }

        String token = ApiSession.getFcmToken(appContext);
        if (!TextUtils.isEmpty(token)) {
            registerToken(appContext, token);
            return;
        }

        syncTokenIfPossible(appContext);
    }

    public static void unregisterCurrentToken(Context context, @NonNull Runnable done) {
        Context appContext = context.getApplicationContext();

        String token = ApiSession.getFcmToken(appContext);
        if (TextUtils.isEmpty(token) || !ApiSession.isLoggedIn(appContext)) {
            done.run();
            return;
        }

        try {
            JSONObject payload = new JSONObject();
            payload.put("token", token);
            payload.put("device_name", deviceName());

            ApiClient.delete(appContext, "/api/users/push-token/", payload, true, new ApiClient.ResponseCallback() {
                @Override
                public void onSuccess(int statusCode, @NonNull String responseBody) {
                    done.run();
                }

                @Override
                public void onError(int statusCode, @NonNull String message, @NonNull String responseBody) {
                    done.run();
                }
            });
        } catch (Exception ignored) {
            done.run();
        }
    }

    private static void registerToken(Context context, String token) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("token", token);
            payload.put("device_name", deviceName());

            ApiClient.post(context, "/api/users/push-token/", payload, true, new ApiClient.ResponseCallback() {
                @Override
                public void onSuccess(int statusCode, @NonNull String responseBody) {
                    // no-op
                }

                @Override
                public void onError(int statusCode, @NonNull String message, @NonNull String responseBody) {
                    // no-op
                }
            });
        } catch (Exception ignored) {
            // no-op
        }
    }

    private static String deviceName() {
        String manufacturer = Build.MANUFACTURER == null ? "" : Build.MANUFACTURER.trim();
        String model = Build.MODEL == null ? "" : Build.MODEL.trim();
        String combined = (manufacturer + " " + model).trim();
        return combined.isEmpty() ? "Android" : combined;
    }
}
