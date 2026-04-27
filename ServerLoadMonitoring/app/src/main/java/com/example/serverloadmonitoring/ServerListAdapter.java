package com.example.serverloadmonitoring;

import android.content.Context;
import android.graphics.Typeface;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.AbsoluteSizeSpan;
import android.text.style.ForegroundColorSpan;
import android.text.style.StyleSpan;
import android.util.TypedValue;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;

import java.util.Collections;
import java.util.List;

public class ServerListAdapter extends RecyclerView.Adapter<ServerListAdapter.ServerViewHolder> {
    public interface Listener {
        void onServerClick(ServerListItem item);

        void onServerMoreClick(ServerListItem item);
    }

    private final Context context;
    private final List<ServerListItem> items;
    private final Listener listener;

    public ServerListAdapter(Context context, List<ServerListItem> items, Listener listener) {
        this.context = context;
        this.items = items;
        this.listener = listener;
    }

    @NonNull
    @Override
    public ServerViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_server_card, parent, false);
        return new ServerViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ServerViewHolder holder, int position) {
        ServerListItem item = items.get(position);

        holder.name.setText(item.getName());
        holder.ip.setText(item.getIp());
        holder.cpu.setText(styleMetricText(item.getCpu()));
        holder.ram.setText(styleMetricText(item.getRam()));
        holder.disk.setText(styleMetricText(item.getDisk()));

        holder.icon.setImageResource(R.drawable.ic_server_rack);

        if (item.isOnline()) {
            holder.status.setText(R.string.server_status_online);
            holder.status.setBackgroundResource(R.drawable.bg_status_online);
            holder.status.setTextColor(ContextCompat.getColor(context, R.color.server_status_online_text));
        } else {
            holder.status.setText(R.string.server_status_offline);
            holder.status.setBackgroundResource(R.drawable.bg_status_offline);
            holder.status.setTextColor(ContextCompat.getColor(context, R.color.server_status_offline_text));
        }

        holder.root.setOnClickListener(v -> listener.onServerClick(item));
        holder.moreButton.setOnClickListener(v -> listener.onServerMoreClick(item));
    }

    @Override
    public int getItemCount() {
        return items.size();
    }

    public void moveItem(int fromPosition, int toPosition) {
        if (fromPosition < 0 || toPosition < 0 || fromPosition >= items.size() || toPosition >= items.size()) {
            return;
        }
        if (fromPosition == toPosition) {
            return;
        }
        Collections.swap(items, fromPosition, toPosition);
        notifyItemMoved(fromPosition, toPosition);
    }

    private SpannableString styleMetricText(String fullText) {
        int splitIndex = fullText.indexOf(' ');
        if (splitIndex <= 0 || splitIndex >= fullText.length() - 1) {
            return new SpannableString(fullText);
        }

        SpannableString styledText = new SpannableString(fullText);
        int labelColor = ContextCompat.getColor(context, R.color.auth_text_secondary);
        int valueColor = ContextCompat.getColor(context, R.color.white);

        styledText.setSpan(
            new ForegroundColorSpan(labelColor),
            0,
            splitIndex,
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
        );
        styledText.setSpan(
            new ForegroundColorSpan(valueColor),
            splitIndex + 1,
            fullText.length(),
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
        );
        styledText.setSpan(
            new StyleSpan(Typeface.BOLD),
            splitIndex + 1,
            fullText.length(),
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
        );
        styledText.setSpan(
            new AbsoluteSizeSpan((int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_SP,
                13f,
                context.getResources().getDisplayMetrics()
            )),
            0,
            fullText.length(),
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
        );
        return styledText;
    }

    static class ServerViewHolder extends RecyclerView.ViewHolder {
        private final View root;
        private final TextView name;
        private final TextView ip;
        private final TextView status;
        private final ImageView moreButton;
        private final TextView cpu;
        private final TextView ram;
        private final TextView disk;
        private final ImageView icon;

        ServerViewHolder(@NonNull View itemView) {
            super(itemView);
            root = itemView.findViewById(R.id.cardServer);
            name = itemView.findViewById(R.id.textServerName);
            ip = itemView.findViewById(R.id.textServerIp);
            status = itemView.findViewById(R.id.textServerStatus);
            moreButton = itemView.findViewById(R.id.buttonServerMore);
            cpu = itemView.findViewById(R.id.textMetricCpu);
            ram = itemView.findViewById(R.id.textMetricRam);
            disk = itemView.findViewById(R.id.textMetricDisk);
            icon = itemView.findViewById(R.id.imageServerIcon);
        }
    }
}
