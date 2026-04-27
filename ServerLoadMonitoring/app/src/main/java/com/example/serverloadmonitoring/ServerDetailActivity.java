package com.example.serverloadmonitoring;

import android.content.SharedPreferences;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.CompoundButton;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.TableLayout;
import android.widget.TableRow;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.graphics.Insets;
import androidx.core.graphics.ColorUtils;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.widget.NestedScrollView;

import com.google.android.material.switchmaterial.SwitchMaterial;
import com.google.android.material.tabs.TabLayout;
import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class ServerDetailActivity extends AppCompatActivity {
    public static final String EXTRA_SERVER_ID = "extra_server_id";
    public static final String EXTRA_SERVER_NAME = "extra_server_name";
    private static final String OVERVIEW_CACHE_PREFS = "server_overview_cache";
    private static final String OVERVIEW_CACHE_KEY_PREFIX = "overview_response_server_";
    private static final long COMMAND_POLL_INTERVAL_MS = 1200L;
    private static final long COMMAND_POLL_TIMEOUT_MS = 30000L;

    private final Map<String, Integer> rangeToMinutes = new LinkedHashMap<>();
    private final Map<String, Boolean> pendingServiceCommands = new HashMap<>();
    private final List<ProcessEntry> processEntries = new ArrayList<>();
    private final List<TableRow> serviceRows = new ArrayList<>();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable overviewRefreshRunnable = new Runnable() {
        @Override
        public void run() {
            loadServerOverview(false);
        }
    };

    private SortColumn activeSortColumn = SortColumn.CPU;
    private boolean sortAscending = false;
    private static final float SERVICE_COL_WEIGHT_NAME = 2.5f;
    private static final float SERVICE_COL_WEIGHT_STATUS = 1.2f;
    private static final float SERVICE_COL_WEIGHT_ENABLED = 1.0f;
    private static final float SERVICE_COL_WEIGHT_ACTIONS = 1.3f;

    private int serverId;
    private String serverName;

    private TextView processHeaderPid;
    private TextView processHeaderName;
    private TextView processHeaderCpu;
    private TextView processHeaderRam;

    private TextView title;
    private TextView metricIntervalValue;
    private TextView processIntervalValue;
    private TextView serviceIntervalValue;

    private TextView overviewCpuValue;
    private TextView overviewCpuLabel;
    private TextView overviewRamValue;
    private TextView overviewRamLabel;
    private TextView overviewDiskValue;
    private TextView overviewDiskLabel;
    private TextView overviewNetworkValue;
    private TextView overviewNetworkUp;
    private TextView overviewNetworkDown;

    private TextView detailHostnameValue;
    private TextView detailOsValue;
    private TextView detailKernelValue;
    private TextView detailIpValue;
    private TextView detailCpuModelValue;
    private TextView detailCoresValue;
    private TextView detailTotalRamValue;
    private TextView detailTotalDiskValue;
    private TextView detailUptimeValue;
    private TextView detailAgentValue;

    private LineChartView viewOverviewCpuChart;
    private LineChartView viewOverviewRamChart;
    private LineChartView viewOverviewDiskChart;
    private LineChartView viewCpuChart;
    private LineChartView viewRamChart;

    private TabLayout tabLayoutDetail;
    private TableLayout serviceTable;
    private TextInputEditText inputServiceSearch;
    private int currentRequestedMinutes = 15;
    private boolean isOverviewLoading;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_server_detail);

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
            Toast.makeText(this, R.string.server_detail_missing_server, Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        ImageButton backButton = findViewById(R.id.buttonBack);
        ImageButton serverMoreButton = findViewById(R.id.buttonServerMore);

        title = findViewById(R.id.textServerTitle);
        metricIntervalValue = findViewById(R.id.textDetailMetricIntervalValue);
        processIntervalValue = findViewById(R.id.textDetailProcessIntervalValue);
        serviceIntervalValue = findViewById(R.id.textDetailServiceIntervalValue);

        overviewCpuValue = findViewById(R.id.textOverviewCpuValue);
        overviewCpuLabel = findViewById(R.id.textOverviewCpuLabel);
        overviewRamValue = findViewById(R.id.textOverviewRamValue);
        overviewRamLabel = findViewById(R.id.textOverviewRamLabel);
        overviewDiskValue = findViewById(R.id.textOverviewDiskValue);
        overviewDiskLabel = findViewById(R.id.textOverviewDiskLabel);
        overviewNetworkValue = findViewById(R.id.textOverviewNetworkValue);
        overviewNetworkUp = findViewById(R.id.textOverviewNetworkUp);
        overviewNetworkDown = findViewById(R.id.textOverviewNetworkDown);

        detailHostnameValue = findViewById(R.id.textDetailHostnameValue);
        detailOsValue = findViewById(R.id.textDetailOsValue);
        detailKernelValue = findViewById(R.id.textDetailKernelValue);
        detailIpValue = findViewById(R.id.textDetailIpValue);
        detailCpuModelValue = findViewById(R.id.textDetailCpuModelValue);
        detailCoresValue = findViewById(R.id.textDetailCoresValue);
        detailTotalRamValue = findViewById(R.id.textDetailTotalRamValue);
        detailTotalDiskValue = findViewById(R.id.textDetailTotalDiskValue);
        detailUptimeValue = findViewById(R.id.textDetailUptimeValue);
        detailAgentValue = findViewById(R.id.textDetailAgentValue);

        viewOverviewCpuChart = findViewById(R.id.viewOverviewCpuChart);
        viewOverviewRamChart = findViewById(R.id.viewOverviewRamChart);
        viewOverviewDiskChart = findViewById(R.id.viewOverviewDiskChart);
        viewCpuChart = findViewById(R.id.viewCpuChart);
        viewRamChart = findViewById(R.id.viewRamChart);

        setupChartColors();

        tabLayoutDetail = findViewById(R.id.tabLayoutDetail);
        AutoCompleteTextView graphRangeInput = findViewById(R.id.inputGraphRange);

        final View overviewContent = findViewById(R.id.contentOverview);
        final View servicesContent = findViewById(R.id.contentServices);
        final View detailsContent = findViewById(R.id.contentDetails);

        serviceTable = findViewById(R.id.serviceTable);
        inputServiceSearch = findViewById(R.id.inputServiceSearch);

        title.setText(serverName);

        backButton.setOnClickListener(v -> finish());
        serverMoreButton.setOnClickListener(v -> {
            Intent intent = new Intent(ServerDetailActivity.this, ServerSettingsActivity.class);
            intent.putExtra(ServerSettingsActivity.EXTRA_SERVER_ID, serverId);
            intent.putExtra(ServerSettingsActivity.EXTRA_SERVER_NAME, serverName);
            startActivity(intent);
        });

        tabLayoutDetail.addTab(tabLayoutDetail.newTab().setText(R.string.detail_tab_overview));
        tabLayoutDetail.addTab(tabLayoutDetail.newTab().setText(R.string.detail_tab_services));
        tabLayoutDetail.addTab(tabLayoutDetail.newTab().setText(R.string.detail_tab_details));

        showTab(0, overviewContent, servicesContent, detailsContent);
        setupSwipeNavigation(overviewContent, servicesContent, detailsContent);
        setupGraphRangeSelector(graphRangeInput);
        setupProcessTableSorting();
        setupServiceSearch();
        if (!loadOverviewFromCache()) {
            applyNoDataState();
        }

        tabLayoutDetail.addOnTabSelectedListener(new TabLayout.OnTabSelectedListener() {
            @Override
            public void onTabSelected(TabLayout.Tab tab) {
                if (tab == null) {
                    return;
                }
                showTab(tab.getPosition(), overviewContent, servicesContent, detailsContent);
            }

            @Override
            public void onTabUnselected(TabLayout.Tab tab) {
                // no-op
            }

            @Override
            public void onTabReselected(TabLayout.Tab tab) {
                // no-op
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        startOverviewAutoRefresh(true);
    }

    @Override
    protected void onPause() {
        super.onPause();
        handler.removeCallbacks(overviewRefreshRunnable);
    }

    private void setupChartColors() {
        int colorCpu = ContextCompat.getColor(this, R.color.auth_accent_light);
        int colorRam = Color.parseColor("#4CAF50");
        int colorDisk = Color.parseColor("#9C27B0");

        viewOverviewCpuChart.setLineColor(colorCpu);
        viewCpuChart.setLineColor(colorCpu);

        viewOverviewRamChart.setLineColor(colorRam);
        viewRamChart.setLineColor(colorRam);

        viewOverviewDiskChart.setLineColor(colorDisk);
    }

    private void startOverviewAutoRefresh(boolean immediate) {
        handler.removeCallbacks(overviewRefreshRunnable);
        if (immediate) {
            loadServerOverview(true);
        } else {
            scheduleNextOverviewRefresh();
        }
    }

    private void scheduleNextOverviewRefresh() {
        handler.removeCallbacks(overviewRefreshRunnable);
        int seconds = Math.max(1, ApiSession.getDataRefreshIntervalSeconds(this));
        handler.postDelayed(overviewRefreshRunnable, seconds * 1000L);
    }

    private void loadServerOverview(boolean showErrors) {
        if (isOverviewLoading) {
            return;
        }
        isOverviewLoading = true;

        String rangeLabel = "15m";
        currentRequestedMinutes = 15;
        AutoCompleteTextView graphRangeInput = findViewById(R.id.inputGraphRange);
        if (graphRangeInput != null && graphRangeInput.getText() != null) {
            String label = graphRangeInput.getText().toString();
            Integer mins = rangeToMinutes.get(label);
            if (mins != null) {
                currentRequestedMinutes = mins;
                rangeLabel = mins + "m";
            }
        }

        ApiClient.get(this, "/api/servers/" + serverId + "/overview/?minutes=" + rangeLabel, true, new ApiClient.ResponseCallback() {
            @Override
            public void onSuccess(int statusCode, String responseBody) {
                isOverviewLoading = false;
                try {
                    JSONObject payload = new JSONObject(responseBody);
                    bindOverviewPayload(payload);
                    saveOverviewToCache(responseBody);
                } catch (Exception exception) {
                    if (showErrors) {
                        Toast.makeText(ServerDetailActivity.this, R.string.server_detail_parse_error, Toast.LENGTH_SHORT).show();
                    }
                }
                scheduleNextOverviewRefresh();
            }

            @Override
            public void onError(int statusCode, String message, String responseBody) {
                isOverviewLoading = false;
                if (statusCode == 401) {
                    ApiSession.clear(ServerDetailActivity.this);
                    openLoginAndFinish();
                    return;
                }
                if (showErrors) {
                    Toast.makeText(ServerDetailActivity.this, message, Toast.LENGTH_SHORT).show();
                }
                scheduleNextOverviewRefresh();
            }
        });
    }

    private void bindOverviewPayload(JSONObject payload) {
        JSONObject server = payload.optJSONObject("server");
        JSONObject latestMetric = payload.optJSONObject("latest_metric");
        JSONArray processes = payload.optJSONArray("processes");
        JSONArray services = payload.optJSONArray("services");
        JSONArray metrics = payload.optJSONArray("metrics");

        if (server != null) {
            String resolvedName = server.optString("name", "");
            if (resolvedName == null || resolvedName.trim().isEmpty()) {
                resolvedName = server.optString("hostname", serverName);
            }
            serverName = resolvedName;
            title.setText(resolvedName);

            detailHostnameValue.setText(emptyToDash(server.optString("hostname", "")));
            detailOsValue.setText(emptyToDash(server.optString("os_name", "")));
            detailKernelValue.setText(emptyToDash(server.optString("kernel_version", "")));
            detailIpValue.setText(emptyToDash(server.optString("ip_address", "")));
            detailCpuModelValue.setText(emptyToDash(server.optString("cpu_model", "")));
            detailCoresValue.setText(formatIntOrDash(server, "cpu_cores"));
            detailTotalRamValue.setText(formatBytes(server.optLong("total_ram_bytes", 0L)));
            detailTotalDiskValue.setText(formatBytes(server.optLong("total_disk_bytes", 0L)));

            int metricInterval = server.optInt("interval_seconds", 5);
            int processInterval = server.optInt("process_snapshot_interval_seconds", 30);
            int serviceInterval = server.optInt("service_snapshot_interval_seconds", 60);
            metricIntervalValue.setText(getString(R.string.detail_seconds_template, metricInterval));
            processIntervalValue.setText(getString(R.string.detail_seconds_template, processInterval));
            serviceIntervalValue.setText(getString(R.string.detail_seconds_template, serviceInterval));

            boolean online = server.optBoolean("is_online", false);
            detailAgentValue.setText(online
                ? getString(R.string.server_detail_agent_online)
                : getString(R.string.server_detail_agent_offline));
            detailAgentValue.setTextColor(ContextCompat.getColor(
                this,
                online ? R.color.server_status_online_text : R.color.server_status_offline_text
            ));
        }

        bindMetric(latestMetric, server);
        bindProcesses(processes);
        rebuildServiceTable(services);

        int interval = server != null ? server.optInt("interval_seconds", 5) : 5;
        bindCharts(metrics, interval);
    }

    private void bindCharts(JSONArray metrics, int intervalSeconds) {
        if (intervalSeconds <= 0) intervalSeconds = 5;
        int expectedCount = (currentRequestedMinutes * 60) / intervalSeconds;
        if (expectedCount < 2) expectedCount = 2;

        List<Float> cpuPoints = new ArrayList<>();
        List<Float> ramPoints = new ArrayList<>();
        List<Float> diskPoints = new ArrayList<>();

        if (metrics != null && metrics.length() > 0) {
            int actualCount = metrics.length();
            
            // OPTIMIZATION: Downsampling for large datasets
            // We want max ~1000 points for smooth performance
            int step = Math.max(1, actualCount / 1000);
            
            if (actualCount < expectedCount) {
                for (int i = 0; i < (expectedCount - actualCount); i += step) {
                    cpuPoints.add(0f);
                    ramPoints.add(0f);
                    diskPoints.add(0f);
                }
            }

            for (int i = 0; i < actualCount; i += step) {
                JSONObject m = metrics.optJSONObject(i);
                if (m != null) {
                    cpuPoints.add((float) m.optDouble("cpu_usage", 0.0));
                    ramPoints.add((float) m.optDouble("ram_usage", 0.0));
                    diskPoints.add((float) m.optDouble("disk_usage", 0.0));
                }
            }
        } else {
            // ... (zbytek zůstává stejný)
            for (int i = 0; i < expectedCount; i++) {
                cpuPoints.add(0f);
                ramPoints.add(0f);
                diskPoints.add(0f);
            }
        }

        viewOverviewCpuChart.setData(cpuPoints, 100f);
        viewCpuChart.setData(cpuPoints, 100f);
        viewOverviewRamChart.setData(ramPoints, 100f);
        viewRamChart.setData(ramPoints, 100f);
        viewOverviewDiskChart.setData(diskPoints, 100f);
    }

    private void saveOverviewToCache(String responseBody) {
        if (responseBody == null || responseBody.trim().isEmpty()) {
            return;
        }
        SharedPreferences preferences = getSharedPreferences(OVERVIEW_CACHE_PREFS, MODE_PRIVATE);
        preferences.edit().putString(cacheKeyForServer(), responseBody).apply();
    }

    private boolean loadOverviewFromCache() {
        SharedPreferences preferences = getSharedPreferences(OVERVIEW_CACHE_PREFS, MODE_PRIVATE);
        String rawPayload = preferences.getString(cacheKeyForServer(), "");
        if (rawPayload == null || rawPayload.trim().isEmpty()) {
            return false;
        }

        try {
            JSONObject payload = new JSONObject(rawPayload);
            bindOverviewPayload(payload);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    private String cacheKeyForServer() {
        return OVERVIEW_CACHE_KEY_PREFIX + serverId;
    }

    private void applyNoDataState() {
        title.setText(serverName);

        detailHostnameValue.setText("--");
        detailOsValue.setText("--");
        detailKernelValue.setText("--");
        detailIpValue.setText("--");
        detailCpuModelValue.setText("--");
        detailCoresValue.setText("--");
        detailTotalRamValue.setText("--");
        detailTotalDiskValue.setText("--");
        detailUptimeValue.setText("--");
        detailAgentValue.setText("--");
        detailAgentValue.setTextColor(ContextCompat.getColor(this, R.color.auth_text_secondary));

        metricIntervalValue.setText("--");
        processIntervalValue.setText("--");
        serviceIntervalValue.setText("--");

        bindMetric(null, null);
        bindProcesses(new JSONArray());
        rebuildServiceTable(new JSONArray());
        bindCharts(null, 5);
    }

    private void bindMetric(JSONObject latestMetric, JSONObject server) {
        if (latestMetric == null) {
            overviewCpuValue.setText("--");
            overviewRamValue.setText("--");
            overviewDiskValue.setText("--");
            overviewNetworkValue.setText("--");
            overviewNetworkUp.setText(getString(R.string.server_detail_network_up_template, "--"));
            overviewNetworkDown.setText(getString(R.string.server_detail_network_down_template, "--"));
            detailUptimeValue.setText("--");
            return;
        }

        double cpu = latestMetric.optDouble("cpu_usage", Double.NaN);
        double ram = latestMetric.optDouble("ram_usage", Double.NaN);
        double disk = latestMetric.optDouble("disk_usage", Double.NaN);

        overviewCpuValue.setText(formatPercentLarge(cpu));
        overviewRamValue.setText(formatPercentLarge(ram));
        overviewDiskValue.setText(formatPercentLarge(disk));

        long totalRamBytes = server != null ? server.optLong("total_ram_bytes", 0L) : 0L;
        long totalDiskBytes = server != null ? server.optLong("total_disk_bytes", 0L) : 0L;

        if (totalRamBytes > 0 && !Double.isNaN(ram)) {
            long usedRam = (long) ((ram / 100.0d) * totalRamBytes);
            overviewRamLabel.setText(getString(
                R.string.server_detail_ratio_template,
                formatBytes(usedRam),
                formatBytes(totalRamBytes)
            ));
        } else {
            overviewRamLabel.setText("--");
        }

        if (totalDiskBytes > 0 && !Double.isNaN(disk)) {
            long usedDisk = (long) ((disk / 100.0d) * totalDiskBytes);
            overviewDiskLabel.setText(getString(
                R.string.server_detail_ratio_template,
                formatBytes(usedDisk),
                formatBytes(totalDiskBytes)
            ));
        } else {
            overviewDiskLabel.setText("--");
        }

        overviewCpuLabel.setText(emptyToDash(server == null ? "" : server.optString("cpu_model", "")));

        int metricInterval = server != null ? Math.max(1, server.optInt("interval_seconds", 5)) : 5;
        long uploadBytes = latestMetric.optLong("network_upload_bytes", 0L);
        long downloadBytes = latestMetric.optLong("network_download_bytes", 0L);

        double uploadMbps = (uploadBytes * 8.0d) / (metricInterval * 1_000_000.0d);
        double downloadMbps = (downloadBytes * 8.0d) / (metricInterval * 1_000_000.0d);
        double totalMbps = uploadMbps + downloadMbps;

        overviewNetworkValue.setText(getString(
            R.string.server_detail_network_total_template,
            trimDecimal(totalMbps)
        ));
        overviewNetworkUp.setText(getString(
            R.string.server_detail_network_up_template,
            trimDecimal(uploadMbps)
        ));
        overviewNetworkDown.setText(getString(
            R.string.server_detail_network_down_template,
            trimDecimal(downloadMbps)
        ));

        long uptimeSeconds = latestMetric.optLong("uptime_seconds", 0L);
        detailUptimeValue.setText(formatUptime(uptimeSeconds));
    }

    private void bindProcesses(JSONArray processes) {
        processEntries.clear();
        if (processes != null) {
            for (int i = 0; i < processes.length(); i++) {
                JSONObject item = processes.optJSONObject(i);
                if (item == null) {
                    continue;
                }
                processEntries.add(new ProcessEntry(
                    item.optInt("pid", 0),
                    item.optString("name", "-"),
                    (float) item.optDouble("cpu_usage", 0.0),
                    (float) item.optDouble("ram_usage", 0.0)
                ));
            }
        }
        renderProcessTable();
    }

    private void rebuildServiceTable(JSONArray services) {
        if (serviceTable == null) {
            return;
        }
        if (hasPendingServiceCommands()) {
            return;
        }

        while (serviceTable.getChildCount() > 1) {
            serviceTable.removeViewAt(1);
        }

        serviceRows.clear();

        if (services != null) {
            for (int i = 0; i < services.length(); i++) {
                JSONObject service = services.optJSONObject(i);
                if (service == null) {
                    continue;
                }
                String rawName = service.optString("name", "");
                String normalizedName = normalizeServiceDisplayName(rawName);
                String status = service.optString("status", "stopped");
                boolean enabled = service.optBoolean("enabled", false);

                TableRow row = buildServiceRow(rawName, normalizedName, status, enabled);
                serviceTable.addView(row);
                serviceRows.add(row);
            }
        }

        filterServicesByName(inputServiceSearch == null ? "" : textFrom(inputServiceSearch));
    }

    private TableRow buildServiceRow(String rawName, String displayName, String status, boolean enabled) {
        TableRow row = new TableRow(this);
        row.setTag(rawName);
        row.setPadding(0, dp(8), 0, dp(8));
        row.setGravity(Gravity.CENTER_VERTICAL);

        TextView nameView = new TextView(this);
        nameView.setText(displayName);
        nameView.setTextColor(ContextCompat.getColor(this, R.color.auth_text_primary));
        nameView.setTextSize(13f);
        nameView.setPadding(dp(10), 0, dp(8), 0);
        nameView.setSingleLine(true);
        nameView.setEllipsize(TextUtils.TruncateAt.END);
        nameView.setLayoutParams(serviceColumnParams(SERVICE_COL_WEIGHT_NAME, Gravity.START | Gravity.CENTER_VERTICAL));

        TextView statusView = new TextView(this);
        statusView.setTextSize(13f);
        statusView.setPadding(dp(8), 0, dp(8), 0);
        statusView.setSingleLine(true);
        statusView.setLayoutParams(serviceColumnParams(SERVICE_COL_WEIGHT_STATUS, Gravity.CENTER));

        SwitchMaterial enabledSwitch = new SwitchMaterial(this);
        enabledSwitch.setChecked(enabled);
        enabledSwitch.setShowText(false);
        enabledSwitch.setScaleX(0.86f);
        enabledSwitch.setScaleY(0.86f);
        enabledSwitch.setTrackTintList(buildServiceSwitchTrackTint());
        enabledSwitch.setThumbTintList(buildServiceSwitchThumbTint());
        enabledSwitch.setLayoutParams(serviceColumnParams(SERVICE_COL_WEIGHT_ENABLED, Gravity.CENTER));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setPadding(0, 0, dp(10), 0);
        actions.setGravity(Gravity.CENTER);
        actions.setLayoutParams(serviceColumnParams(SERVICE_COL_WEIGHT_ACTIONS, Gravity.CENTER));

        ImageButton startButton = buildServiceActionButton(R.drawable.ic_play_18);

        ImageButton stopButton = buildServiceActionButton(R.drawable.ic_stop_18);
        LinearLayout.LayoutParams stopParams = (LinearLayout.LayoutParams) stopButton.getLayoutParams();
        stopParams.setMarginStart(dp(6));
        stopButton.setLayoutParams(stopParams);

        actions.addView(startButton);
        actions.addView(stopButton);

        final boolean[] runningState = new boolean[]{isServiceRunning(status)};
        final boolean[] commandInFlight = new boolean[]{false};

        bindServiceStatus(statusView, runningState[0]);
        applyServiceRowActionState(startButton, stopButton, runningState[0], commandInFlight[0]);

        CompoundButton.OnCheckedChangeListener[] switchListenerHolder = new CompoundButton.OnCheckedChangeListener[1];
        CompoundButton.OnCheckedChangeListener switchListener = new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                if (!buttonView.isPressed() || commandInFlight[0]) {
                    return;
                }

                commandInFlight[0] = true;
                enabledSwitch.setEnabled(false);
                bindServicePending(statusView);
                applyServiceRowActionState(startButton, stopButton, runningState[0], true);
                markServiceCommandPending(rawName);

                final boolean requestedChecked = isChecked;
                sendServiceCommand(
                    requestedChecked ? "enable" : "disable",
                    rawName,
                    commandId -> waitForCommandCompletion(
                        commandId,
                        () -> {
                            clearServiceCommandPending(rawName);
                            commandInFlight[0] = false;
                            enabledSwitch.setEnabled(true);
                            bindServiceStatus(statusView, runningState[0]);
                            applyServiceRowActionState(startButton, stopButton, runningState[0], false);
                            requestFastOverviewRefresh();
                            Toast.makeText(
                                ServerDetailActivity.this,
                                R.string.server_detail_command_success,
                                Toast.LENGTH_SHORT
                            ).show();
                        },
                        failureMessage -> {
                            clearServiceCommandPending(rawName);
                            commandInFlight[0] = false;
                            enabledSwitch.setEnabled(true);
                            enabledSwitch.setOnCheckedChangeListener(null);
                            enabledSwitch.setChecked(!requestedChecked);
                            enabledSwitch.setOnCheckedChangeListener(switchListenerHolder[0]);
                            bindServiceStatus(statusView, runningState[0]);
                            applyServiceRowActionState(startButton, stopButton, runningState[0], false);
                            Toast.makeText(ServerDetailActivity.this, failureMessage, Toast.LENGTH_SHORT).show();
                            requestFastOverviewRefresh();
                        }
                    ),
                    () -> {
                        clearServiceCommandPending(rawName);
                        commandInFlight[0] = false;
                        enabledSwitch.setEnabled(true);
                        enabledSwitch.setOnCheckedChangeListener(null);
                        enabledSwitch.setChecked(!requestedChecked);
                        enabledSwitch.setOnCheckedChangeListener(switchListenerHolder[0]);
                        bindServiceStatus(statusView, runningState[0]);
                        applyServiceRowActionState(startButton, stopButton, runningState[0], false);
                    }
                );
            }
        };
        switchListenerHolder[0] = switchListener;
        enabledSwitch.setOnCheckedChangeListener(switchListener);

        startButton.setOnClickListener(v -> {
            if (commandInFlight[0] || runningState[0]) {
                return;
            }
            animateServiceActionPress(startButton);
            commandInFlight[0] = true;
            enabledSwitch.setEnabled(false);
            bindServicePending(statusView);
            applyServiceRowActionState(startButton, stopButton, runningState[0], true);
            markServiceCommandPending(rawName);
            final boolean previousRunning = runningState[0];
            sendServiceCommand(
                "start",
                rawName,
                commandId -> waitForCommandCompletion(
                    commandId,
                    () -> {
                        clearServiceCommandPending(rawName);
                        commandInFlight[0] = false;
                        runningState[0] = true;
                        enabledSwitch.setEnabled(true);
                        bindServiceStatus(statusView, true);
                        applyServiceRowActionState(startButton, stopButton, true, false);
                        requestFastOverviewRefresh();
                        Toast.makeText(
                            ServerDetailActivity.this,
                            R.string.server_detail_command_success,
                            Toast.LENGTH_SHORT
                        ).show();
                    },
                    failureMessage -> {
                        clearServiceCommandPending(rawName);
                        commandInFlight[0] = false;
                        runningState[0] = previousRunning;
                        enabledSwitch.setEnabled(true);
                        bindServiceStatus(statusView, previousRunning);
                        applyServiceRowActionState(startButton, stopButton, previousRunning, false);
                        Toast.makeText(ServerDetailActivity.this, failureMessage, Toast.LENGTH_SHORT).show();
                        requestFastOverviewRefresh();
                    }
                ),
                () -> {
                    clearServiceCommandPending(rawName);
                    commandInFlight[0] = false;
                    enabledSwitch.setEnabled(true);
                    runningState[0] = previousRunning;
                    bindServiceStatus(statusView, previousRunning);
                    applyServiceRowActionState(startButton, stopButton, previousRunning, false);
                }
            );
        });

        stopButton.setOnClickListener(v -> {
            if (commandInFlight[0] || !runningState[0]) {
                return;
            }
            animateServiceActionPress(stopButton);
            commandInFlight[0] = true;
            enabledSwitch.setEnabled(false);
            bindServicePending(statusView);
            applyServiceRowActionState(startButton, stopButton, runningState[0], true);
            markServiceCommandPending(rawName);
            final boolean previousRunning = runningState[0];
            sendServiceCommand(
                "stop",
                rawName,
                commandId -> waitForCommandCompletion(
                    commandId,
                    () -> {
                        clearServiceCommandPending(rawName);
                        commandInFlight[0] = false;
                        runningState[0] = false;
                        enabledSwitch.setEnabled(true);
                        bindServiceStatus(statusView, false);
                        applyServiceRowActionState(startButton, stopButton, false, false);
                        requestFastOverviewRefresh();
                        Toast.makeText(
                            ServerDetailActivity.this,
                            R.string.server_detail_command_success,
                            Toast.LENGTH_SHORT
                        ).show();
                    },
                    failureMessage -> {
                        clearServiceCommandPending(rawName);
                        commandInFlight[0] = false;
                        runningState[0] = previousRunning;
                        enabledSwitch.setEnabled(true);
                        bindServiceStatus(statusView, previousRunning);
                        applyServiceRowActionState(startButton, stopButton, previousRunning, false);
                        Toast.makeText(ServerDetailActivity.this, failureMessage, Toast.LENGTH_SHORT).show();
                        requestFastOverviewRefresh();
                    }
                ),
                () -> {
                    clearServiceCommandPending(rawName);
                    commandInFlight[0] = false;
                    enabledSwitch.setEnabled(true);
                    runningState[0] = previousRunning;
                    bindServiceStatus(statusView, previousRunning);
                    applyServiceRowActionState(startButton, stopButton, previousRunning, false);
                }
            );
        });

        row.addView(nameView);
        row.addView(statusView);
        row.addView(enabledSwitch);
        row.addView(actions);

        return row;
    }

    private String serviceCommandKey(String rawServiceName) {
        String normalized = normalizeServiceDisplayName(rawServiceName);
        return normalized.toLowerCase(Locale.ROOT);
    }

    private void markServiceCommandPending(String rawServiceName) {
        pendingServiceCommands.put(serviceCommandKey(rawServiceName), Boolean.TRUE);
    }

    private void clearServiceCommandPending(String rawServiceName) {
        pendingServiceCommands.remove(serviceCommandKey(rawServiceName));
    }

    private boolean hasPendingServiceCommands() {
        return !pendingServiceCommands.isEmpty();
    }

    private TableRow.LayoutParams serviceColumnParams(float weight, int gravity) {
        TableRow.LayoutParams params = new TableRow.LayoutParams(0, TableRow.LayoutParams.WRAP_CONTENT, weight);
        params.gravity = gravity;
        return params;
    }

    private ImageButton buildServiceActionButton(int iconResId) {
        ImageButton button = new ImageButton(this);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(dp(30), dp(30));
        button.setLayoutParams(params);
        button.setBackgroundResource(R.drawable.bg_service_action_button);
        button.setImageResource(iconResId);
        button.setScaleType(ImageButton.ScaleType.CENTER_INSIDE);
        button.setPadding(dp(7), dp(7), dp(7), dp(7));
        return button;
    }

    private void sendServiceCommand(
        String action,
        String rawServiceName,
        CommandQueuedCallback onQueued,
        Runnable onError
    ) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("action", action);
            payload.put("service", rawServiceName);

            ApiClient.post(this, "/api/servers/" + serverId + "/commands/", payload, true, new ApiClient.ResponseCallback() {
                @Override
                public void onSuccess(int statusCode, String responseBody) {
                    try {
                        JSONObject responseJson = new JSONObject(responseBody);
                        int commandId = responseJson.optInt("id", 0);
                        if (commandId <= 0) {
                            throw new IllegalStateException("Missing command ID.");
                        }
                        if (onQueued != null) {
                            onQueued.onQueued(commandId);
                        }
                    } catch (Exception parseError) {
                        if (onError != null) {
                            onError.run();
                        }
                        Toast.makeText(
                            ServerDetailActivity.this,
                            R.string.server_detail_parse_error,
                            Toast.LENGTH_SHORT
                        ).show();
                    }
                }

                @Override
                public void onError(int statusCode, String message, String responseBody) {
                    if (onError != null) {
                        onError.run();
                    }
                    if (statusCode == 401) {
                        ApiSession.clear(ServerDetailActivity.this);
                        openLoginAndFinish();
                        return;
                    }
                    Toast.makeText(ServerDetailActivity.this, message, Toast.LENGTH_SHORT).show();
                }
            });
        } catch (Exception exception) {
            if (onError != null) {
                onError.run();
            }
            Toast.makeText(this, R.string.auth_error_unexpected, Toast.LENGTH_SHORT).show();
        }
    }

    private void waitForCommandCompletion(int commandId, Runnable onSuccess, CommandFailedCallback onFailed) {
        long deadlineMs = System.currentTimeMillis() + COMMAND_POLL_TIMEOUT_MS;
        pollCommandStatus(commandId, deadlineMs, onSuccess, onFailed);
    }

    private void pollCommandStatus(
        int commandId,
        long deadlineMs,
        Runnable onSuccess,
        CommandFailedCallback onFailed
    ) {
        if (System.currentTimeMillis() > deadlineMs) {
            if (onFailed != null) {
                onFailed.onFailed(getString(R.string.server_detail_command_timeout));
            }
            return;
        }

        ApiClient.get(
            this,
            "/api/servers/" + serverId + "/commands/" + commandId + "/",
            true,
            new ApiClient.ResponseCallback() {
                @Override
                public void onSuccess(int statusCode, String responseBody) {
                    try {
                        JSONObject payload = new JSONObject(responseBody);
                        String commandStatus = payload.optString("status", "pending").trim().toLowerCase(Locale.ROOT);
                        if ("pending".equals(commandStatus)) {
                            handler.postDelayed(
                                () -> pollCommandStatus(commandId, deadlineMs, onSuccess, onFailed),
                                COMMAND_POLL_INTERVAL_MS
                            );
                            return;
                        }
                        if ("success".equals(commandStatus)) {
                            if (onSuccess != null) {
                                onSuccess.run();
                            }
                            return;
                        }

                        String failure = extractCommandFailureMessage(payload);
                        if (onFailed != null) {
                            onFailed.onFailed(failure);
                        }
                    } catch (Exception parseError) {
                        if (onFailed != null) {
                            onFailed.onFailed(getString(R.string.server_detail_parse_error));
                        }
                    }
                }

                @Override
                public void onError(int statusCode, String message, String responseBody) {
                    if (statusCode == 401) {
                        ApiSession.clear(ServerDetailActivity.this);
                        openLoginAndFinish();
                        return;
                    }
                    if (System.currentTimeMillis() > deadlineMs) {
                        if (onFailed != null) {
                            onFailed.onFailed(TextUtils.isEmpty(message)
                                ? getString(R.string.server_detail_command_timeout)
                                : message);
                        }
                        return;
                    }
                    handler.postDelayed(
                        () -> pollCommandStatus(commandId, deadlineMs, onSuccess, onFailed),
                        COMMAND_POLL_INTERVAL_MS
                    );
                }
            }
        );
    }

    private String extractCommandFailureMessage(JSONObject payload) {
        if (payload == null) {
            return getString(R.string.server_detail_command_failed);
        }

        String error = payload.optString("error", "").trim();
        if (!error.isEmpty()) {
            return error;
        }

        String stderr = payload.optString("stderr", "").trim();
        if (!stderr.isEmpty()) {
            return stderr;
        }

        int returnCode = payload.optInt("return_code", Integer.MIN_VALUE);
        if (returnCode != Integer.MIN_VALUE) {
            return getString(R.string.server_detail_command_failed) + " (code " + returnCode + ")";
        }

        return getString(R.string.server_detail_command_failed);
    }

    private void bindServiceStatus(TextView statusView, boolean running) {
        statusView.setText(running ? R.string.detail_services_running : R.string.detail_services_stopped);
        statusView.setTextColor(ContextCompat.getColor(
            this,
            running ? R.color.server_status_online_text : R.color.server_status_offline_text
        ));
    }

    private void bindServicePending(TextView statusView) {
        statusView.setText(R.string.detail_services_pending);
        statusView.setTextColor(ContextCompat.getColor(this, R.color.auth_text_hint));
    }

    private void applyServiceRowActionState(
        ImageButton startButton,
        ImageButton stopButton,
        boolean isRunning,
        boolean isBusy
    ) {
        boolean startEnabled = !isBusy && !isRunning;
        boolean stopEnabled = !isBusy && isRunning;
        styleServiceActionButton(startButton, startEnabled, R.color.server_status_online_text);
        styleServiceActionButton(stopButton, stopEnabled, R.color.server_status_offline_text);
    }

    private void styleServiceActionButton(ImageButton button, boolean isEnabled, int accentColorRes) {
        int accentColor = ContextCompat.getColor(this, accentColorRes);
        int iconColor = isEnabled ? accentColor : ContextCompat.getColor(this, R.color.auth_text_hint);
        int backgroundColor = isEnabled
            ? ColorUtils.setAlphaComponent(accentColor, 54)
            : ContextCompat.getColor(this, R.color.auth_input_bg);

        button.setEnabled(isEnabled);
        button.setClickable(isEnabled);
        button.setAlpha(isEnabled ? 1f : 0.42f);
        button.setImageTintList(ColorStateList.valueOf(iconColor));
        button.setBackgroundTintList(ColorStateList.valueOf(backgroundColor));
    }

    private void animateServiceActionPress(View actionButton) {
        actionButton.animate().cancel();
        actionButton.animate()
            .scaleX(0.88f)
            .scaleY(0.88f)
            .setDuration(70L)
            .withEndAction(() -> actionButton.animate().scaleX(1f).scaleY(1f).setDuration(130L).start())
            .start();
    }

    private void requestFastOverviewRefresh() {
        handler.removeCallbacks(overviewRefreshRunnable);
        loadServerOverview(false);
        handler.postDelayed(() -> loadServerOverview(false), 900L);
    }

    private ColorStateList buildServiceSwitchTrackTint() {
        int checked = ContextCompat.getColor(this, R.color.auth_accent_light);
        int unchecked = ColorUtils.setAlphaComponent(ContextCompat.getColor(this, R.color.auth_text_hint), 140);
        int disabled = ColorUtils.setAlphaComponent(ContextCompat.getColor(this, R.color.auth_text_hint), 90);
        return new ColorStateList(
            new int[][]{
                new int[]{-android.R.attr.state_enabled},
                new int[]{android.R.attr.state_checked},
                new int[]{}
            },
            new int[]{disabled, checked, unchecked}
        );
    }

    private ColorStateList buildServiceSwitchThumbTint() {
        int checked = ContextCompat.getColor(this, R.color.auth_text_primary);
        int unchecked = ColorUtils.setAlphaComponent(ContextCompat.getColor(this, R.color.auth_text_primary), 210);
        int disabled = ColorUtils.setAlphaComponent(ContextCompat.getColor(this, R.color.auth_text_hint), 150);
        return new ColorStateList(
            new int[][]{
                new int[]{-android.R.attr.state_enabled},
                new int[]{android.R.attr.state_checked},
                new int[]{}
            },
            new int[]{disabled, checked, unchecked}
        );
    }

    private void setupSwipeNavigation(View overviewContent, View servicesContent, View detailsContent) {
        GestureDetector swipeDetector = new GestureDetector(
            this,
            new GestureDetector.SimpleOnGestureListener() {
                private static final int MIN_DISTANCE_PX = 80;
                private static final int MIN_VELOCITY_PX = 120;

                @Override
                public boolean onDown(MotionEvent e) {
                    return true;
                }

                @Override
                public boolean onFling(MotionEvent e1, MotionEvent e2, float velocityX, float velocityY) {
                    if (e1 == null || e2 == null) {
                        return false;
                    }
                    float distanceX = e2.getX() - e1.getX();
                    float distanceY = e2.getY() - e1.getY();

                    boolean mostlyHorizontal = Math.abs(distanceX) > Math.abs(distanceY) * 1.15f;
                    boolean enoughDistance = Math.abs(distanceX) > MIN_DISTANCE_PX;
                    boolean enoughVelocity = Math.abs(velocityX) > MIN_VELOCITY_PX;
                    if (!mostlyHorizontal || !enoughDistance || !enoughVelocity) {
                        return false;
                    }

                    if (distanceX < 0) {
                        moveToAdjacentTab(+1);
                    } else {
                        moveToAdjacentTab(-1);
                    }
                    return true;
                }
            }
        );

        View.OnTouchListener touchListener = (v, event) -> {
            swipeDetector.onTouchEvent(event);
            return false;
        };
        overviewContent.setOnTouchListener(touchListener);
        servicesContent.setOnTouchListener(touchListener);
        detailsContent.setOnTouchListener(touchListener);
    }

    private void moveToAdjacentTab(int delta) {
        if (tabLayoutDetail == null || tabLayoutDetail.getTabCount() == 0) {
            return;
        }
        int current = tabLayoutDetail.getSelectedTabPosition();
        if (current < 0) {
            current = 0;
        }
        int target = current + delta;
        if (target < 0 || target >= tabLayoutDetail.getTabCount()) {
            return;
        }
        TabLayout.Tab tab = tabLayoutDetail.getTabAt(target);
        if (tab != null) {
            tab.select();
        }
    }

    private void showTab(int position, View overview, View services, View details) {
        View[] pages = new View[]{overview, services, details};
        if (position < 0 || position >= pages.length) {
            return;
        }

        int currentVisible = -1;
        for (int i = 0; i < pages.length; i++) {
            pages[i].animate().cancel();
            if (pages[i].getVisibility() == View.VISIBLE) {
                currentVisible = i;
            }
        }

        if (currentVisible == position) {
            pages[position].setAlpha(1f);
            pages[position].setTranslationX(0f);
            return;
        }

        View incoming = pages[position];
        if (currentVisible == -1) {
            for (int i = 0; i < pages.length; i++) {
                pages[i].setVisibility(i == position ? View.VISIBLE : View.GONE);
                pages[i].setAlpha(1f);
                pages[i].setTranslationX(0f);
            }
            return;
        }

        View outgoing = pages[currentVisible];
        float direction = position > currentVisible ? 1f : -1f;

        incoming.setVisibility(View.VISIBLE);
        incoming.setAlpha(0f);
        incoming.setTranslationX(28f * direction);
        incoming.animate()
            .alpha(1f)
            .translationX(0f)
            .setDuration(190)
            .start();

        outgoing.animate()
            .alpha(0f)
            .translationX(-28f * direction)
            .setDuration(190)
            .withEndAction(() -> {
                outgoing.setVisibility(View.GONE);
                outgoing.setAlpha(1f);
                outgoing.setTranslationX(0f);
            })
            .start();

        for (int i = 0; i < pages.length; i++) {
            if (i != position && i != currentVisible) {
                pages[i].setVisibility(View.GONE);
                pages[i].setAlpha(1f);
                pages[i].setTranslationX(0f);
            }
        }
    }

    private void setupGraphRangeSelector(AutoCompleteTextView graphRangeInput) {
        String last5m = getString(R.string.detail_graph_range_5m);
        String last15m = getString(R.string.detail_graph_range_15m);
        String last1h = getString(R.string.detail_graph_range_1h);
        String last6h = getString(R.string.detail_graph_range_6h);
        String last24h = getString(R.string.detail_graph_range_24h);

        rangeToMinutes.clear();
        rangeToMinutes.put(last5m, 5);
        rangeToMinutes.put(last15m, 15);
        rangeToMinutes.put(last1h, 60);
        rangeToMinutes.put(last6h, 360);
        rangeToMinutes.put(last24h, 1440);

        String[] labels = rangeToMinutes.keySet().toArray(new String[0]);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, labels);
        graphRangeInput.setAdapter(adapter);

        graphRangeInput.setText(last15m, false);
        updateChartRange(last15m);

        graphRangeInput.setOnItemClickListener((parent, view, position, id) -> {
            String selected = adapter.getItem(position);
            if (selected != null) {
                updateChartRange(selected);
                loadServerOverview(true);
            }
        });

        graphRangeInput.addTextChangedListener(new TextWatcher() {
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
                if (s == null) {
                    return;
                }
                String label = s.toString().trim();
                if (rangeToMinutes.containsKey(label)) {
                    updateChartRange(label);
                }
            }
        });
    }

    private void updateChartRange(String label) {
        Integer minutes = rangeToMinutes.get(label);
        if (minutes == null) {
            minutes = 15;
        }

        TextView cpuSubtitle = findViewById(R.id.textCpuChartSubtitle);
        TextView ramSubtitle = findViewById(R.id.textRamChartSubtitle);
        cpuSubtitle.setText(getString(R.string.detail_chart_subtitle_template, label));
        ramSubtitle.setText(getString(R.string.detail_chart_subtitle_template, label));

        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("HH:mm", Locale.getDefault());
        LocalTime end = LocalTime.now().withSecond(0).withNano(0);
        LocalTime start = end.minusMinutes(minutes);
        LocalTime mid = start.plusMinutes(minutes / 2L);

        ((TextView) findViewById(R.id.chartCpuXStart)).setText(start.format(formatter));
        ((TextView) findViewById(R.id.chartCpuXMid)).setText(mid.format(formatter));
        ((TextView) findViewById(R.id.chartCpuXEnd)).setText(end.format(formatter));

        ((TextView) findViewById(R.id.chartRamXStart)).setText(start.format(formatter));
        ((TextView) findViewById(R.id.chartRamXMid)).setText(mid.format(formatter));
        ((TextView) findViewById(R.id.chartRamXEnd)).setText(end.format(formatter));
    }

    private void setupProcessTableSorting() {
        NestedScrollView overview = findViewById(R.id.contentOverview);
        if (overview == null || overview.getChildCount() == 0 || !(overview.getChildAt(0) instanceof LinearLayout)) {
            return;
        }

        LinearLayout overviewRoot = (LinearLayout) overview.getChildAt(0);
        if (overviewRoot.getChildCount() < 6) {
            return;
        }

        View topProcessesCard = overviewRoot.getChildAt(5);
        if (!(topProcessesCard instanceof com.google.android.material.card.MaterialCardView)) {
            return;
        }

        View cardContent = ((com.google.android.material.card.MaterialCardView) topProcessesCard).getChildAt(0);
        if (!(cardContent instanceof LinearLayout)) {
            return;
        }

        LinearLayout topProcessesContainer = (LinearLayout) cardContent;
        if (topProcessesContainer.getChildCount() < 4) {
            return;
        }

        View headerView = topProcessesContainer.getChildAt(1);
        if (!(headerView instanceof LinearLayout)) {
            return;
        }

        LinearLayout headerRow = (LinearLayout) headerView;
        if (headerRow.getChildCount() < 4) {
            return;
        }

        processHeaderPid = (TextView) headerRow.getChildAt(0);
        processHeaderName = (TextView) headerRow.getChildAt(1);
        processHeaderCpu = (TextView) headerRow.getChildAt(2);
        processHeaderRam = (TextView) headerRow.getChildAt(3);

        processHeaderPid.setOnClickListener(v -> onSortColumnClicked(SortColumn.PID));
        processHeaderName.setOnClickListener(v -> onSortColumnClicked(SortColumn.NAME));
        processHeaderCpu.setOnClickListener(v -> onSortColumnClicked(SortColumn.CPU));
        processHeaderRam.setOnClickListener(v -> onSortColumnClicked(SortColumn.RAM));
    }

    private void setupServiceSearch() {
        if (inputServiceSearch == null) {
            return;
        }

        inputServiceSearch.addTextChangedListener(new TextWatcher() {
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
                filterServicesByName(s == null ? "" : s.toString());
            }
        });
    }

    private void filterServicesByName(String query) {
        String normalizedQuery = query == null ? "" : query.trim().toLowerCase(Locale.getDefault());
        for (TableRow row : serviceRows) {
            if (row.getChildCount() == 0 || !(row.getChildAt(0) instanceof TextView)) {
                continue;
            }
            TextView serviceNameView = (TextView) row.getChildAt(0);
            String serviceName = serviceNameView.getText() == null
                ? ""
                : serviceNameView.getText().toString().toLowerCase(Locale.getDefault());
            boolean isMatch = normalizedQuery.isEmpty() || serviceName.contains(normalizedQuery);
            row.setVisibility(isMatch ? View.VISIBLE : View.GONE);
        }
    }

    private void onSortColumnClicked(SortColumn column) {
        if (activeSortColumn == column) {
            sortAscending = !sortAscending;
        } else {
            activeSortColumn = column;
            sortAscending = true;
        }
        renderProcessTable();
    }

    private void renderProcessTable() {
        NestedScrollView overview = findViewById(R.id.contentOverview);
        if (overview == null || overview.getChildCount() == 0 || !(overview.getChildAt(0) instanceof LinearLayout)) {
            return;
        }
        LinearLayout overviewRoot = (LinearLayout) overview.getChildAt(0);
        if (overviewRoot.getChildCount() < 6) {
            return;
        }
        View topProcessesCard = overviewRoot.getChildAt(5);
        if (!(topProcessesCard instanceof com.google.android.material.card.MaterialCardView)) {
            return;
        }
        View cardContent = ((com.google.android.material.card.MaterialCardView) topProcessesCard).getChildAt(0);
        if (!(cardContent instanceof LinearLayout)) {
            return;
        }

        LinearLayout container = (LinearLayout) cardContent;

        List<ProcessEntry> sorted = new ArrayList<>(processEntries);
        Comparator<ProcessEntry> comparator = buildComparator(activeSortColumn);
        if (!sortAscending) {
            comparator = comparator.reversed();
        }
        sorted.sort(comparator);

        final int firstDataRowIndex = 3;
        final int maxRows = 10;

        for (int i = 0; i < maxRows; i++) {
            int rowIndex = firstDataRowIndex + i;
            if (rowIndex >= container.getChildCount()) {
                break;
            }
            View rowView = container.getChildAt(rowIndex);
            if (!(rowView instanceof LinearLayout)) {
                continue;
            }
            LinearLayout row = (LinearLayout) rowView;
            if (row.getChildCount() < 4) {
                continue;
            }

            TextView pidCell = (TextView) row.getChildAt(0);
            TextView nameCell = (TextView) row.getChildAt(1);
            TextView cpuCell = (TextView) row.getChildAt(2);
            TextView ramCell = (TextView) row.getChildAt(3);

            if (i < sorted.size()) {
                ProcessEntry entry = sorted.get(i);
                pidCell.setText(String.valueOf(entry.pid));
                nameCell.setText(entry.name);
                cpuCell.setText(formatPercent(entry.cpuUsage));
                ramCell.setText(formatPercent(entry.ramUsage));
            } else {
                pidCell.setText("");
                nameCell.setText("");
                cpuCell.setText("");
                ramCell.setText("");
            }
        }

        updateProcessHeaderLabels();
    }

    private Comparator<ProcessEntry> buildComparator(SortColumn column) {
        switch (column) {
            case PID:
                return Comparator.comparingInt(item -> item.pid);
            case NAME:
                return (a, b) -> a.name.compareToIgnoreCase(b.name);
            case RAM:
                return Comparator.comparingDouble(item -> item.ramUsage);
            case CPU:
            default:
                return Comparator.comparingDouble(item -> item.cpuUsage);
        }
    }

    private void updateProcessHeaderLabels() {
        if (processHeaderPid == null || processHeaderName == null || processHeaderCpu == null || processHeaderRam == null) {
            return;
        }

        processHeaderPid.setText(buildHeaderLabel("PID", SortColumn.PID));
        processHeaderName.setText(buildHeaderLabel("NAME", SortColumn.NAME));
        processHeaderCpu.setText(buildHeaderLabel("CPU%", SortColumn.CPU));
        processHeaderRam.setText(buildHeaderLabel("RAM%", SortColumn.RAM));

        int defaultColor = ContextCompat.getColor(this, R.color.auth_text_hint);
        int activeColor = ContextCompat.getColor(this, R.color.auth_accent_light);

        processHeaderPid.setTextColor(activeSortColumn == SortColumn.PID ? activeColor : defaultColor);
        processHeaderName.setTextColor(activeSortColumn == SortColumn.NAME ? activeColor : defaultColor);
        processHeaderCpu.setTextColor(activeSortColumn == SortColumn.CPU ? activeColor : defaultColor);
        processHeaderRam.setTextColor(activeSortColumn == SortColumn.RAM ? activeColor : defaultColor);
    }

    private String buildHeaderLabel(String base, SortColumn column) {
        if (column != activeSortColumn) {
            return base;
        }
        return sortAscending ? base + " ^" : base + " v";
    }

    private boolean isServiceRunning(String status) {
        String normalized = (status == null ? "" : status.trim().toLowerCase(Locale.ROOT));
        return "running".equals(normalized) || "active".equals(normalized) || "online".equals(normalized);
    }

    private String normalizeServiceDisplayName(String rawName) {
        if (rawName == null) {
            return "-";
        }
        String trimmed = rawName.trim();
        if (trimmed.endsWith(".service")) {
            return trimmed.substring(0, trimmed.length() - ".service".length());
        }
        return trimmed;
    }

    private String formatPercent(float value) {
        String formatted = String.format(Locale.getDefault(), "%.1f", value);
        return formatted.replace('.', ',');
    }

    private String formatPercentLarge(double value) {
        if (Double.isNaN(value)) {
            return "--";
        }
        return trimDecimal(value) + "%";
    }

    private String trimDecimal(double value) {
        String formatted = String.format(Locale.US, "%.1f", value);
        if (formatted.endsWith(".0")) {
            return formatted.substring(0, formatted.length() - 2);
        }
        return formatted;
    }

    private String formatBytes(long bytes) {
        if (bytes <= 0) {
            return "--";
        }

        double value = bytes;
        String unit = "B";

        if (value >= 1024d) {
            value /= 1024d;
            unit = "KB";
        }
        if (value >= 1024d) {
            value /= 1024d;
            unit = "MB";
        }
        if (value >= 1024d) {
            value /= 1024d;
            unit = "GB";
        }
        if (value >= 1024d) {
            value /= 1024d;
            unit = "TB";
        }

        return trimDecimal(value) + " " + unit;
    }

    private String formatUptime(long totalSeconds) {
        if (totalSeconds <= 0) {
            return "--";
        }

        long days = totalSeconds / 86_400L;
        long hours = (totalSeconds % 86_400L) / 3_600L;
        long minutes = (totalSeconds % 3_600L) / 60L;

        if (days > 0) {
            return days + "d " + hours + "h " + minutes + "m";
        }
        if (hours > 0) {
            return hours + "h " + minutes + "m";
        }
        return minutes + "m";
    }

    private String emptyToDash(String value) {
        if (value == null) {
            return "--";
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? "--" : trimmed;
    }

    private String formatIntOrDash(JSONObject object, String key) {
        if (object == null || !object.has(key) || object.isNull(key)) {
            return "--";
        }
        return String.valueOf(object.optInt(key));
    }

    private String textFrom(TextInputEditText input) {
        return input.getText() == null ? "" : input.getText().toString();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density);
    }

    private void openLoginAndFinish() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
        finish();
    }

    private enum SortColumn {
        PID,
        NAME,
        CPU,
        RAM
    }

    private interface CommandQueuedCallback {
        void onQueued(int commandId);
    }

    private interface CommandFailedCallback {
        void onFailed(String message);
    }

    private static final class ProcessEntry {
        final int pid;
        final String name;
        final float cpuUsage;
        final float ramUsage;

        ProcessEntry(int pid, String name, float cpuUsage, float ramUsage) {
            this.pid = pid;
            this.name = name;
            this.cpuUsage = cpuUsage;
            this.ramUsage = ramUsage;
        }
    }
}
