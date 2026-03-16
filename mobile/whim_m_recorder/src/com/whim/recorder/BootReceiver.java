package com.whim.recorder;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            // Launch Whim.m on boot
            Intent launch = new Intent(context, MainActivity.class);
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(launch);

            // Prompt Tailscale to connect (opens Tailscale app intent)
            try {
                Intent tailscale = context.getPackageManager()
                    .getLaunchIntentForPackage("com.tailscale.ipn");
                if (tailscale != null) {
                    tailscale.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    context.startActivity(tailscale);
                }
            } catch (Exception e) {
                // Tailscale not installed or can't be launched
            }
        }
    }
}
