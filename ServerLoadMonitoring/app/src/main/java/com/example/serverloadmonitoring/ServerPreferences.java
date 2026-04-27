package com.example.serverloadmonitoring;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Locale;

public final class ServerPreferences {
    private static final String PREFS_NAME = "server_local_settings";

    private static final int DEFAULT_METRIC_INTERVAL_SECONDS = 5;
    private static final int DEFAULT_PROCESS_INTERVAL_SECONDS = 30;
    private static final int DEFAULT_SERVICE_INTERVAL_SECONDS = 60;
    private static final int DEFAULT_DATA_RETENTION_DAYS = 30;
    private static final int DEFAULT_CPU_THRESHOLD_PERCENT = 85;
    private static final int DEFAULT_RAM_THRESHOLD_PERCENT = 90;

    private ServerPreferences() {
    }

    public static ServerSettings load(Context context, String serverKey, String fallbackServerName) {
        SharedPreferences preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        String normalizedKey = normalizeServerKey(serverKey);

        ServerSettings settings = new ServerSettings();
        settings.serverName = preferences.getString(
            key(normalizedKey, "server_name"),
            fallbackServerName
        );
        settings.metricIntervalSeconds = preferences.getInt(
            key(normalizedKey, "metric_interval_seconds"),
            DEFAULT_METRIC_INTERVAL_SECONDS
        );
        settings.processIntervalSeconds = preferences.getInt(
            key(normalizedKey, "process_interval_seconds"),
            DEFAULT_PROCESS_INTERVAL_SECONDS
        );
        settings.serviceIntervalSeconds = preferences.getInt(
            key(normalizedKey, "service_interval_seconds"),
            DEFAULT_SERVICE_INTERVAL_SECONDS
        );
        settings.dataRetentionDays = preferences.getInt(
            key(normalizedKey, "data_retention_days"),
            DEFAULT_DATA_RETENTION_DAYS
        );
        settings.notifyOffline = preferences.getBoolean(
            key(normalizedKey, "notify_offline"),
            true
        );
        settings.cpuThresholdPercent = preferences.getInt(
            key(normalizedKey, "cpu_threshold_percent"),
            DEFAULT_CPU_THRESHOLD_PERCENT
        );
        settings.ramThresholdPercent = preferences.getInt(
            key(normalizedKey, "ram_threshold_percent"),
            DEFAULT_RAM_THRESHOLD_PERCENT
        );

        return settings;
    }

    public static void save(Context context, String serverKey, ServerSettings settings) {
        SharedPreferences preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        String normalizedKey = normalizeServerKey(serverKey);

        preferences.edit()
            .putString(key(normalizedKey, "server_name"), settings.serverName)
            .putInt(key(normalizedKey, "metric_interval_seconds"), settings.metricIntervalSeconds)
            .putInt(key(normalizedKey, "process_interval_seconds"), settings.processIntervalSeconds)
            .putInt(key(normalizedKey, "service_interval_seconds"), settings.serviceIntervalSeconds)
            .putInt(key(normalizedKey, "data_retention_days"), settings.dataRetentionDays)
            .putBoolean(key(normalizedKey, "notify_offline"), settings.notifyOffline)
            .putInt(key(normalizedKey, "cpu_threshold_percent"), settings.cpuThresholdPercent)
            .putInt(key(normalizedKey, "ram_threshold_percent"), settings.ramThresholdPercent)
            .apply();
    }

    public static int parsePositiveOrDefault(String rawValue, int defaultValue, int minimumValue, int maximumValue) {
        if (rawValue == null) {
            return defaultValue;
        }

        String trimmedValue = rawValue.trim();
        if (trimmedValue.isEmpty()) {
            return defaultValue;
        }

        try {
            int parsed = Integer.parseInt(trimmedValue);
            if (parsed < minimumValue) {
                return minimumValue;
            }
            if (parsed > maximumValue) {
                return maximumValue;
            }
            return parsed;
        } catch (NumberFormatException ignored) {
            return defaultValue;
        }
    }

    public static String normalizeServerKey(String serverName) {
        if (serverName == null) {
            return "server_default";
        }

        String trimmed = serverName.trim();
        if (trimmed.isEmpty()) {
            return "server_default";
        }

        String lower = trimmed.toLowerCase(Locale.ROOT);
        return lower.replaceAll("[^a-z0-9]+", "_");
    }

    private static String key(String normalizedServerKey, String fieldName) {
        return normalizedServerKey + "__" + fieldName;
    }

    public static final class ServerSettings {
        public String serverName;
        public int metricIntervalSeconds;
        public int processIntervalSeconds;
        public int serviceIntervalSeconds;
        public int dataRetentionDays;
        public boolean notifyOffline;
        public int cpuThresholdPercent;
        public int ramThresholdPercent;
    }
}
