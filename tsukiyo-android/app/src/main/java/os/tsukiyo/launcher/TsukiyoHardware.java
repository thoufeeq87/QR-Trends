package os.tsukiyo.launcher;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.wifi.ScanResult;
import android.net.wifi.WifiInfo;
import android.net.wifi.WifiManager;
import android.net.wifi.WifiNetworkSpecifier;
import android.os.Build;
import android.content.ContentValues;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Environment;
import android.provider.MediaStore;
import android.provider.Settings;
import android.telephony.TelephonyManager;
import android.util.Base64;
import android.widget.Toast;
import java.io.OutputStream;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Lets the Tsukiyo OS page read real Wi-Fi and Bluetooth hardware. The page finds it as window.TsukiyoHW.
 * Everything returns JSON text. Nothing here stores a password: it goes straight to Android.
 */
@SuppressLint({"MissingPermission", "deprecation"})
public class TsukiyoHardware {
    private static final int REQ_LOCATION = 21;
    private static final int REQ_BT = 22;

    private final Activity act;
    private final WebView web;
    private final WifiManager wifi;
    private final ConnectivityManager cm;
    private ConnectivityManager.NetworkCallback joinCb;

    public TsukiyoHardware(Activity activity, WebView webView) {
        this.act = activity;
        this.web = webView;
        this.wifi = (WifiManager) activity.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        this.cm = (ConnectivityManager) activity.getSystemService(Context.CONNECTIVITY_SERVICE);
    }

    private boolean hasLocation() {
        return act.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    /** Is the radio on, is the phone on a Wi-Fi network, and which one. */
    @JavascriptInterface
    public String wifiInfo() {
        JSONObject o = new JSONObject();
        try {
            boolean enabled = wifi != null && wifi.isWifiEnabled();
            boolean connected = false;
            String ssid = "";
            Network n = cm.getActiveNetwork();
            NetworkCapabilities caps = n == null ? null : cm.getNetworkCapabilities(n);
            if (caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                    && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) {
                connected = true;
                if (hasLocation()) {
                    WifiInfo wi = wifi.getConnectionInfo();
                    if (wi != null && wi.getSSID() != null) {
                        ssid = wi.getSSID().replace("\"", "");
                        if ("<unknown ssid>".equals(ssid)) ssid = "";
                    }
                }
            }
            o.put("enabled", enabled);
            o.put("connected", connected);
            o.put("ssid", ssid);
        } catch (Exception e) {
            // report nothing rather than guess
        }
        return o.toString();
    }

    /** Starts a scan and returns the latest results: [{ssid, level, secure}]. Needs the location permission. */
    @JavascriptInterface
    public String wifiScan() {
        JSONArray arr = new JSONArray();
        try {
            if (!hasLocation()) {
                act.runOnUiThread(() -> act.requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, REQ_LOCATION));
                return arr.toString();
            }
            wifi.startScan();
            List<ScanResult> results = wifi.getScanResults();
            Map<String, JSONObject> best = new HashMap<>();
            for (ScanResult r : results) {
                String ssid = r.SSID;
                if (ssid == null || ssid.isEmpty()) continue;
                JSONObject prev = best.get(ssid);
                if (prev != null && prev.getInt("level") >= r.level) continue;
                String cap = r.capabilities == null ? "" : r.capabilities;
                JSONObject o = new JSONObject();
                o.put("ssid", ssid);
                o.put("level", r.level);
                o.put("secure", cap.contains("WPA") || cap.contains("WEP") || cap.contains("SAE") || cap.contains("PSK") || cap.contains("EAP"));
                best.put(ssid, o);
            }
            for (JSONObject o : best.values()) arr.put(o);
        } catch (Exception e) {
            // empty list
        }
        return arr.toString();
    }

    /**
     * Joins a network. Android 10 and newer show their own confirmation. The answer arrives later as
     * window.__tsukiyoWifiResult('{"ssid":"..","ok":true}') or with ok:false and an error text.
     * Note: this connects this app to that network; the system Wi-Fi settings stay the way to switch the whole phone.
     */
    @JavascriptInterface
    public String wifiConnect(final String ssid, final String password) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            reply(ssid, false, "Joining a network from an app needs Android 10 or newer. Use the Wi-Fi settings of Android.");
            return "unsupported";
        }
        try {
            WifiNetworkSpecifier.Builder spec = new WifiNetworkSpecifier.Builder().setSsid(ssid);
            if (password != null && !password.isEmpty()) spec.setWpa2Passphrase(password);
            NetworkRequest req = new NetworkRequest.Builder()
                    .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                    .setNetworkSpecifier(spec.build())
                    .build();
            if (joinCb != null) {
                try { cm.unregisterNetworkCallback(joinCb); } catch (Exception ignored) { }
            }
            joinCb = new ConnectivityManager.NetworkCallback() {
                @Override
                public void onAvailable(Network network) {
                    cm.bindProcessToNetwork(network);
                    reply(ssid, true, null);
                }

                @Override
                public void onUnavailable() {
                    reply(ssid, false, "Could not join. Check the password and try again.");
                }
            };
            cm.requestNetwork(req, joinCb, 30000);
            return "started";
        } catch (Exception e) {
            reply(ssid, false, "Could not start joining this network.");
            return "error";
        }
    }

    /** Paired Bluetooth devices: [{name, address}]. */
    @JavascriptInterface
    public String btBonded() {
        JSONArray arr = new JSONArray();
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                    && act.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                act.runOnUiThread(() -> act.requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, REQ_BT));
                return arr.toString();
            }
            BluetoothManager bm = (BluetoothManager) act.getSystemService(Context.BLUETOOTH_SERVICE);
            BluetoothAdapter adapter = bm == null ? null : bm.getAdapter();
            if (adapter == null) return arr.toString();
            Set<BluetoothDevice> devices = adapter.getBondedDevices();
            for (BluetoothDevice d : devices) {
                JSONObject o = new JSONObject();
                o.put("name", d.getName());
                o.put("address", d.getAddress());
                arr.put(o);
            }
        } catch (Exception e) {
            // empty list
        }
        return arr.toString();
    }

    @JavascriptInterface
    public void openBtSettings() {
        act.runOnUiThread(() -> act.startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS)));
    }

    @JavascriptInterface
    public void openWifiSettings() {
        act.runOnUiThread(() -> act.startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS)));
    }


    /** True when a SIM card is in the phone and ready. (A web page cannot see this; only the app can.) */
    @JavascriptInterface
    public boolean simPresent() {
        try {
            TelephonyManager tm = (TelephonyManager) act.getSystemService(Context.TELEPHONY_SERVICE);
            if (tm == null) return false;
            int st = tm.getSimState();
            return st != TelephonyManager.SIM_STATE_ABSENT && st != TelephonyManager.SIM_STATE_UNKNOWN && st != TelephonyManager.SIM_STATE_NOT_READY;
        } catch (Exception e) {
            return false;
        }
    }

    /** Real battery numbers: {level, charging, health, tempC, voltage}. */
    @JavascriptInterface
    public String battery() {
        JSONObject o = new JSONObject();
        try {
            Intent b = act.registerReceiver(null, new android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            if (b != null) {
                int level = b.getIntExtra(BatteryManager.EXTRA_LEVEL, -1), scale = b.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
                int status = b.getIntExtra(BatteryManager.EXTRA_STATUS, -1), health = b.getIntExtra(BatteryManager.EXTRA_HEALTH, -1);
                o.put("level", scale > 0 ? Math.round(level * 100f / scale) : level);
                o.put("charging", status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL);
                o.put("health", health == BatteryManager.BATTERY_HEALTH_GOOD ? "good" : health == BatteryManager.BATTERY_HEALTH_OVERHEAT ? "overheat" : health == BatteryManager.BATTERY_HEALTH_DEAD ? "dead" : "unknown");
                o.put("tempC", b.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) / 10.0);
                o.put("voltage", b.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0));
            }
        } catch (Exception e) {
            // report what we have
        }
        return o.toString();
    }

    /** Saves a file the page made (a backup, a photo) into the Downloads folder. Called by the app's download handler. */
    @JavascriptInterface
    public void saveDownload(final String base64, final String mime) {
        try {
            byte[] data = Base64.decode(base64, Base64.DEFAULT);
            String ext = mime != null && mime.startsWith("image/png") ? ".png" : mime != null && mime.startsWith("image/") ? ".jpg" : mime != null && mime.startsWith("video/") ? ".webm" : ".tsukiyo";
            final String name = "tsukiyo-" + System.currentTimeMillis() + ext;
            ContentValues v = new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME, name);
            v.put(MediaStore.Downloads.MIME_TYPE, mime == null ? "application/octet-stream" : mime);
            v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
            Uri uri = act.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            if (uri == null) return;
            try (OutputStream out = act.getContentResolver().openOutputStream(uri)) { out.write(data); }
            act.runOnUiThread(() -> Toast.makeText(act, "Saved to Downloads: " + name, Toast.LENGTH_LONG).show());
        } catch (Exception e) {
            act.runOnUiThread(() -> Toast.makeText(act, "Could not save the file.", Toast.LENGTH_LONG).show());
        }
    }

    private void reply(String ssid, boolean ok, String error) {
        try {
            JSONObject o = new JSONObject();
            o.put("ssid", ssid);
            o.put("ok", ok);
            if (error != null) o.put("error", error);
            final String js = "window.__tsukiyoWifiResult && window.__tsukiyoWifiResult(" + JSONObject.quote(o.toString()) + ")";
            act.runOnUiThread(() -> web.evaluateJavascript(js, null));
        } catch (Exception ignored) {
        }
    }
}
