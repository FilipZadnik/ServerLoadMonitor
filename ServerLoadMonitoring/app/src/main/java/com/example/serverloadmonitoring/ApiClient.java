package com.example.serverloadmonitoring;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Iterator;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ApiClient {
    public interface ResponseCallback {
        void onSuccess(int statusCode, @NonNull String responseBody);

        void onError(int statusCode, @NonNull String message, @NonNull String responseBody);
    }

    private static final int CONNECT_TIMEOUT_MS = 10_000;
    private static final int READ_TIMEOUT_MS = 15_000;

    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor();
    private static final Handler MAIN_THREAD = new Handler(Looper.getMainLooper());

    private ApiClient() {
    }

    public static void get(Context context, String path, boolean requiresAuth, ResponseCallback callback) {
        request(context, "GET", path, null, requiresAuth, true, callback);
    }

    public static void post(
        Context context,
        String path,
        @Nullable JSONObject body,
        boolean requiresAuth,
        ResponseCallback callback
    ) {
        request(context, "POST", path, body, requiresAuth, true, callback);
    }

    public static void patch(
        Context context,
        String path,
        @Nullable JSONObject body,
        boolean requiresAuth,
        ResponseCallback callback
    ) {
        request(context, "PATCH", path, body, requiresAuth, true, callback);
    }

    public static void delete(Context context, String path, boolean requiresAuth, ResponseCallback callback) {
        request(context, "DELETE", path, null, requiresAuth, true, callback);
    }

    public static void delete(
        Context context,
        String path,
        @Nullable JSONObject body,
        boolean requiresAuth,
        ResponseCallback callback
    ) {
        request(context, "DELETE", path, body, requiresAuth, true, callback);
    }

    private static void request(
        Context context,
        String method,
        String path,
        @Nullable JSONObject body,
        boolean requiresAuth,
        boolean allowRefresh,
        ResponseCallback callback
    ) {
        Context appContext = context.getApplicationContext();
        EXECUTOR.execute(() -> {
            String accessToken = requiresAuth ? ApiSession.getAccessToken(appContext) : null;
            HttpResult result = executeRequest(method, path, body, accessToken);

            if (requiresAuth && result.statusCode == HttpURLConnection.HTTP_UNAUTHORIZED && allowRefresh) {
                boolean refreshed = refreshAccessToken(appContext);
                if (refreshed) {
                    accessToken = ApiSession.getAccessToken(appContext);
                    result = executeRequest(method, path, body, accessToken);
                }
            }

            final HttpResult finalResult = result;
            MAIN_THREAD.post(() -> {
                if (finalResult.isSuccessful()) {
                    callback.onSuccess(finalResult.statusCode, finalResult.responseBody);
                    return;
                }
                callback.onError(
                    finalResult.statusCode,
                    parseErrorMessage(finalResult.responseBody, finalResult.fallbackErrorMessage),
                    finalResult.responseBody
                );
            });
        });
    }

    private static HttpResult executeRequest(
        String method,
        String path,
        @Nullable JSONObject body,
        @Nullable String accessToken
    ) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(buildUrl(path));
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod(method);
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setRequestProperty("Accept", "application/json");

            if (!TextUtils.isEmpty(accessToken)) {
                connection.setRequestProperty("Authorization", "Bearer " + accessToken);
            }

            if (body != null) {
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream outputStream = connection.getOutputStream()) {
                    outputStream.write(payload);
                }
            }

            int statusCode = connection.getResponseCode();
            String responseBody = readStreamSafely(statusCode < 400 ? connection.getInputStream() : connection.getErrorStream());
            return new HttpResult(statusCode, responseBody, "");
        } catch (IOException exception) {
            return new HttpResult(0, "", exception.getMessage() == null ? "Network error." : exception.getMessage());
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private static boolean refreshAccessToken(Context context) {
        String refreshToken = ApiSession.getRefreshToken(context);
        if (TextUtils.isEmpty(refreshToken)) {
            return false;
        }

        JSONObject body = new JSONObject();
        try {
            body.put("refresh", refreshToken);
        } catch (Exception ignored) {
            return false;
        }

        HttpResult refreshResult = executeRequest("POST", "/api/auth/refresh/", body, null);
        if (!refreshResult.isSuccessful()) {
            return false;
        }

        try {
            JSONObject payload = new JSONObject(refreshResult.responseBody);
            String newAccessToken = payload.optString("access", "");
            if (TextUtils.isEmpty(newAccessToken)) {
                return false;
            }
            ApiSession.setAccessToken(context, newAccessToken);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    private static String readStreamSafely(@Nullable InputStream stream) throws IOException {
        if (stream == null) {
            return "";
        }

        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        return builder.toString();
    }

    private static String buildUrl(String path) {
        String normalizedPath = path.startsWith("/") ? path : "/" + path;
        return ApiConfig.BASE_URL.replaceAll("/+$", "") + normalizedPath;
    }

    private static String parseErrorMessage(String responseBody, String fallback) {
        if (!TextUtils.isEmpty(responseBody)) {
            try {
                JSONObject payload = new JSONObject(responseBody);
                String detail = payload.optString("detail", "");
                if (!TextUtils.isEmpty(detail)) {
                    return detail;
                }

                Iterator<String> keys = payload.keys();
                if (keys.hasNext()) {
                    String key = keys.next();
                    Object value = payload.opt(key);
                    String message = null;

                    if (value instanceof JSONArray) {
                        JSONArray array = (JSONArray) value;
                        if (array.length() > 0) {
                            message = array.optString(0, null);
                        }
                    } else if (value != null) {
                        message = value.toString();
                    }

                    if (message != null) {
                        if ("password".equals(key)) {
                            message = message.replace("toto pole", "heslo");
                        }
                        return message;
                    }
                }
            } catch (Exception ignored) {
                // no-op
            }
        }

        if (!TextUtils.isEmpty(fallback)) {
            return fallback;
        }
        return "Request failed.";
    }

    private static final class HttpResult {
        final int statusCode;
        final String responseBody;
        final String fallbackErrorMessage;

        HttpResult(int statusCode, String responseBody, String fallbackErrorMessage) {
            this.statusCode = statusCode;
            this.responseBody = responseBody == null ? "" : responseBody;
            this.fallbackErrorMessage = fallbackErrorMessage == null ? "" : fallbackErrorMessage;
        }

        boolean isSuccessful() {
            return statusCode >= 200 && statusCode < 300;
        }
    }
}
