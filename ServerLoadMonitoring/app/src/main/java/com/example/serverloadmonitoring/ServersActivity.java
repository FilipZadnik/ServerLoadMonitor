package com.example.serverloadmonitoring;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.ImageButton;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.recyclerview.widget.ItemTouchHelper;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class ServersActivity extends AppCompatActivity {
    private static final int REQUEST_CODE_POST_NOTIFICATIONS = 201;

    private final List<ServerListItem> serverItems = new ArrayList<>();
    private final Handler refreshHandler = new Handler(Looper.getMainLooper());

    private ServerListAdapter adapter;
    private boolean reorderChanged;
    private boolean isLoading;
    private boolean isDraggingServer;

    private final Runnable refreshRunnable = new Runnable() {
        @Override
        public void run() {
            fetchServers(false);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_servers);

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });

        if (!ApiSession.isLoggedIn(this)) {
            openLoginAndFinish();
            return;
        }

        ImageButton addServerButton = findViewById(R.id.buttonAddServer);
        ImageButton menuButton = findViewById(R.id.buttonMenu);

        addServerButton.setOnClickListener(v -> startActivity(new Intent(ServersActivity.this, AddServerActivity.class)));
        menuButton.setOnClickListener(v -> {
            startActivity(new Intent(ServersActivity.this, GlobalSettingsActivity.class));
            overridePendingTransition(0, 0);
        });

        RecyclerView recyclerView = findViewById(R.id.recyclerServers);
        recyclerView.setLayoutManager(new LinearLayoutManager(this));

        adapter = new ServerListAdapter(this, serverItems, new ServerListAdapter.Listener() {
            @Override
            public void onServerClick(ServerListItem item) {
                openServerDetail(item);
            }

            @Override
            public void onServerMoreClick(ServerListItem item) {
                openServerSettings(item);
            }
        });
        recyclerView.setAdapter(adapter);

        ItemTouchHelper itemTouchHelper = new ItemTouchHelper(new ItemTouchHelper.SimpleCallback(
            ItemTouchHelper.UP | ItemTouchHelper.DOWN,
            0
        ) {
            @Override
            public boolean onMove(
                RecyclerView recyclerView,
                RecyclerView.ViewHolder viewHolder,
                RecyclerView.ViewHolder target
            ) {
                int fromPosition = viewHolder.getBindingAdapterPosition();
                int toPosition = target.getBindingAdapterPosition();
                adapter.moveItem(fromPosition, toPosition);
                reorderChanged = true;
                return true;
            }

            @Override
            public void onSwiped(RecyclerView.ViewHolder viewHolder, int direction) {
                // no-op
            }

            @Override
            public boolean isLongPressDragEnabled() {
                return true;
            }

            @Override
            public void onSelectedChanged(RecyclerView.ViewHolder viewHolder, int actionState) {
                super.onSelectedChanged(viewHolder, actionState);
                if (actionState == ItemTouchHelper.ACTION_STATE_DRAG) {
                    isDraggingServer = true;
                    refreshHandler.removeCallbacks(refreshRunnable);
                }
            }

            @Override
            public void clearView(RecyclerView recyclerView, RecyclerView.ViewHolder viewHolder) {
                super.clearView(recyclerView, viewHolder);
                isDraggingServer = false;
                if (reorderChanged) {
                    reorderChanged = false;
                    persistOrderToBackend();
                }
                startAutoRefresh(true);
            }
        });
        itemTouchHelper.attachToRecyclerView(recyclerView);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!ApiSession.isLoggedIn(this)) {
            openLoginAndFinish();
            return;
        }
        requestNotificationPermissionIfNeeded();
        NotificationTokenManager.registerKnownTokenIfLoggedIn(this);
        NotificationTokenManager.syncTokenIfPossible(this);
        startAutoRefresh(true);
    }

    @Override
    protected void onStop() {
        super.onStop();
        refreshHandler.removeCallbacks(refreshRunnable);
    }

    private void startAutoRefresh(boolean immediate) {
        refreshHandler.removeCallbacks(refreshRunnable);
        if (immediate) {
            fetchServers(true);
        } else {
            scheduleNextRefresh();
        }
    }

    private void scheduleNextRefresh() {
        if (isDraggingServer) {
            return;
        }
        int seconds = Math.max(1, ApiSession.getDataRefreshIntervalSeconds(this));
        refreshHandler.postDelayed(refreshRunnable, seconds * 1000L);
    }

    private void fetchServers(boolean showErrors) {
        if (isLoading || isDraggingServer) {
            return;
        }

        isLoading = true;
        ApiClient.get(this, "/api/servers/", true, new ApiClient.ResponseCallback() {
            @Override
            public void onSuccess(int statusCode, String responseBody) {
                isLoading = false;
                if (isDraggingServer) {
                    scheduleNextRefresh();
                    return;
                }
                try {
                    JSONArray array = new JSONArray(responseBody);
                    serverItems.clear();
                    for (int i = 0; i < array.length(); i++) {
                        JSONObject item = array.optJSONObject(i);
                        if (item == null) {
                            continue;
                        }
                        serverItems.add(mapServer(item));
                    }
                    adapter.notifyDataSetChanged();
                } catch (Exception exception) {
                    if (showErrors) {
                        Toast.makeText(ServersActivity.this, R.string.servers_error_parse, Toast.LENGTH_SHORT).show();
                    }
                }
                scheduleNextRefresh();
            }

            @Override
            public void onError(int statusCode, String message, String responseBody) {
                isLoading = false;
                if (statusCode == 401) {
                    ApiSession.clear(ServersActivity.this);
                    openLoginAndFinish();
                    return;
                }
                if (showErrors) {
                    Toast.makeText(ServersActivity.this, message, Toast.LENGTH_SHORT).show();
                }
                scheduleNextRefresh();
            }
        });
    }

    private ServerListItem mapServer(JSONObject item) {
        int id = item.optInt("id", 0);
        String hostname = item.optString("hostname", "Server");
        String name = item.optString("name", "");
        if (name == null || name.trim().isEmpty()) {
            name = hostname;
        }
        String ip = item.optString("ip_address", "-");
        boolean isOnline = item.optBoolean("is_online", false);

        JSONObject latestMetric = item.optJSONObject("latest_metric");
        String cpu = formatMetric("CPU", latestMetric, "cpu_usage");
        String ram = formatMetric("RAM", latestMetric, "ram_usage");
        String disk = formatMetric("Disk", latestMetric, "disk_usage");

        return new ServerListItem(id, "server_" + id, name, ip, cpu, ram, disk, isOnline);
    }

    private String formatMetric(String label, JSONObject metric, String key) {
        if (metric == null || !metric.has(key)) {
            return label + " --";
        }
        double value = metric.optDouble(key, Double.NaN);
        if (Double.isNaN(value)) {
            return label + " --";
        }

        String text;
        if (Math.abs(value - Math.rint(value)) < 0.05) {
            text = String.format(Locale.getDefault(), "%.0f", value);
        } else {
            text = String.format(Locale.getDefault(), "%.1f", value);
        }
        return label + " " + text + "%";
    }

    private void persistOrderToBackend() {
        try {
            JSONArray ids = new JSONArray();
            for (ServerListItem item : serverItems) {
                ids.put(item.getId());
            }
            JSONObject payload = new JSONObject();
            payload.put("server_ids", ids);
            ApiClient.patch(this, "/api/servers/reorder/", payload, true, new ApiClient.ResponseCallback() {
                @Override
                public void onSuccess(int statusCode, String responseBody) {
                    // no-op
                }

                @Override
                public void onError(int statusCode, String message, String responseBody) {
                    Toast.makeText(ServersActivity.this, message, Toast.LENGTH_SHORT).show();
                }
            });
        } catch (Exception exception) {
            Toast.makeText(this, R.string.servers_error_reorder, Toast.LENGTH_SHORT).show();
        }
    }

    private void openServerDetail(ServerListItem item) {
        Intent intent = new Intent(ServersActivity.this, ServerDetailActivity.class);
        intent.putExtra(ServerDetailActivity.EXTRA_SERVER_ID, item.getId());
        intent.putExtra(ServerDetailActivity.EXTRA_SERVER_NAME, item.getName());
        startActivity(intent);
    }

    private void openServerSettings(ServerListItem item) {
        Intent intent = new Intent(ServersActivity.this, ServerSettingsActivity.class);
        intent.putExtra(ServerSettingsActivity.EXTRA_SERVER_ID, item.getId());
        intent.putExtra(ServerSettingsActivity.EXTRA_SERVER_NAME, item.getName());
        startActivity(intent);
    }

    private void openLoginAndFinish() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
        finish();
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
