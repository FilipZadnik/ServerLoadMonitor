package com.example.serverloadmonitoring;

public class ServerListItem {
    private final int id;
    private final String key;
    private final String name;
    private final String ip;
    private final String cpu;
    private final String ram;
    private final String disk;
    private final boolean online;

    public ServerListItem(int id, String key, String name, String ip, String cpu, String ram, String disk, boolean online) {
        this.id = id;
        this.key = key;
        this.name = name;
        this.ip = ip;
        this.cpu = cpu;
        this.ram = ram;
        this.disk = disk;
        this.online = online;
    }

    public int getId() {
        return id;
    }

    public String getKey() {
        return key;
    }

    public String getName() {
        return name;
    }

    public String getIp() {
        return ip;
    }

    public String getCpu() {
        return cpu;
    }

    public String getRam() {
        return ram;
    }

    public String getDisk() {
        return disk;
    }

    public boolean isOnline() {
        return online;
    }
}
