package com.marketinsight.ai;

import android.content.Context;
import android.os.VibrationEffect;
import android.os.Vibrator;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * Market Insight AI V4.0 Native Java Engine
 * Handles low-latency Black-Scholes calculations and native device tactile triggers.
 */
@CapacitorPlugin(name = "StockPredictor")
public class StockPredictorPlugin extends Plugin {

    @PluginMethod
    public void calculateBlackScholesDelta(PluginCall call) {
        Double spotPrice = call.getDouble("spotPrice", 100.0);
        Double strikePrice = call.getDouble("strikePrice", 100.0);
        Double timeToExpiry = call.getDouble("timeToExpiryYears", 0.038); // ~2 days to Friday
        Double volatility = call.getDouble("volatility", 0.35);
        Double riskFreeRate = call.getDouble("riskFreeRate", 0.052);

        try {
            double d1 = (Math.log(spotPrice / strikePrice) + (riskFreeRate + 0.5 * Math.pow(volatility, 2)) * timeToExpiry) 
                        / (volatility * Math.sqrt(timeToExpiry));
            
            double callDelta = cumulativeNormalDistribution(d1);
            double putDelta = callDelta - 1.0;

            JSObject result = new JSObject();
            result.put("callDelta", Math.round(callDelta * 1000.0) / 1000.0);
            result.put("putDelta", Math.round(putDelta * 1000.0) / 1000.0);
            result.put("status", "SUCCESS");

            call.resolve(result);
        } catch (Exception e) {
            call.reject("Failed to compute Black-Scholes Delta: " + e.getMessage());
        }
    }

    @PluginMethod
    public void triggerHapticFeedback(PluginCall call) {
        Context context = getContext();
        Vibrator vibrator = (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
        
        if (vibrator != null && vibrator.hasVibrator()) {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(45, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                vibrator.vibrate(45);
            }
        }
        call.resolve();
    }

    // Cumulative Normal Distribution approximation function
    private double cumulativeNormalDistribution(double z) {
        double b1 = 0.319381530;
        double b2 = -0.356563782;
        double b3 = 1.781477937;
        double b4 = -1.821255978;
        double b5 = 1.330274429;
        double p = 0.2316419;
        double c2 = 0.39894228;

        if (z >= 0.0) {
            double t = 1.0 / (1.0 + p * z);
            return (1.0 - c2 * Math.exp(-z * z / 2.0) * t * (t * (t * (t * (t * b5 + b4) + b3) + b2) + b1));
        } else {
            double t = 1.0 / (1.0 - p * z);
            return (c2 * Math.exp(-z * z / 2.0) * t * (t * (t * (t * (t * b5 + b4) + b3) + b2) + b1));
        }
    }
}
