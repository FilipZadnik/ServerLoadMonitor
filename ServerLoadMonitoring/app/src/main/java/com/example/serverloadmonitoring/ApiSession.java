package com.example.serverloadmonitoring;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.TextUtils;

import org.json.JSONObject;

public final class ApiSession {
    private static final String PREFS_NAME = "api_session";

    private static final String KEY_ACCESS = "access_token";
    private static final String KEY_REFRESH = "refresh_token";
    private static final String KEY_USER_ID = "user_id";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_EMAIL = "email";
    private static final String KEY_REFRESH_INTERVAL = "data_refresh_interval_seconds";
    private static final String KEY_FCM_TOKEN = "fcm_token";

    private static final int DEFAULT_REFRESH_INTERVAL_SECONDS = 5;

    private ApiSession() {
    }

    public static boolean isLoggedIn(Context context) {
        return !TextUtils.isEmpty(getAccessToken(context));
    }

    public static String getAccessToken(Context context) {
        return prefs(context).getString(KEY_ACCESS, "");
    }

    public static String getRefreshToken(Context context) {
        return prefs(context).getString(KEY_REFRESH, "");
    }

    public static int getUserId(Context context) {
        return prefs(context).getInt(KEY_USER_ID, 0);
    }

    public static String getUsername(Context context) {
        return prefs(context).getString(KEY_USERNAME, "");
    }

    public static String getEmail(Context context) {
        return prefs(context).getString(KEY_EMAIL, "");
    }

    public static int getDataRefreshIntervalSeconds(Context context) {
        return prefs(context).getInt(KEY_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL_SECONDS);
    }

    public static String getFcmToken(Context context) {
        return prefs(context).getString(KEY_FCM_TOKEN, "");
    }

    public static void setAccessToken(Context context, String accessToken) {
        prefs(context).edit().putString(KEY_ACCESS, accessToken == null ? "" : accessToken).apply();
    }

    public static void setDataRefreshIntervalSeconds(Context context, int seconds) {
        int clamped = Math.max(1, seconds);
        prefs(context).edit().putInt(KEY_REFRESH_INTERVAL, clamped).apply();
    }

    public static void setFcmToken(Context context, String token) {
        prefs(context).edit().putString(KEY_FCM_TOKEN, token == null ? "" : token).apply();
    }

    public static void clear(Context context) {
        prefs(context).edit().clear().apply();
    }

    public static void saveAuthPayload(Context context, JSONObject payload) {
        if (payload == null) {
            return;
        }

        String access = payload.optString("access", "");
        String refresh = payload.optString("refresh", "");

        JSONObject user = payload.optJSONObject("user");
        int userId = user != null ? user.optInt("id", 0) : 0;
        String username = user != null ? user.optString("username", "") : "";
        String email = user != null ? user.optString("email", "") : "";

        JSONObject settings = payload.optJSONObject("settings");
        int refreshInterval = settings != null
            ? settings.optInt("data_refresh_interval_seconds", DEFAULT_REFRESH_INTERVAL_SECONDS)
            : DEFAULT_REFRESH_INTERVAL_SECONDS;

        prefs(context).edit()
            .putString(KEY_ACCESS, access)
            .putString(KEY_REFRESH, refresh)
            .putInt(KEY_USER_ID, userId)
            .putString(KEY_USERNAME, username)
            .putString(KEY_EMAIL, email)
            .putInt(KEY_REFRESH_INTERVAL, Math.max(1, refreshInterval))
            .apply();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }
}
