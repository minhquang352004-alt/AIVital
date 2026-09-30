import numpy as np
import time
from scipy import signal
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.signal.filter import butter_bandpass_filter
from aivitals_engine.config import settings

def synthesize_rgb(n_samples, fs, pulse_amp=0.01, light_amp=0.0, noise_amp=0.01):
    t = np.arange(n_samples) / fs
    # Pulse signal (clean)
    pulse = pulse_amp * np.sin(2 * np.pi * 1.2 * t)
    # Light variation (e.g., 0.5 Hz)
    light = light_amp * np.sin(2 * np.pi * 0.5 * t)
    
    # Base skin color (approximate)
    skin_dc = np.array([120, 80, 70])
    
    # Blood volume vector (typical for pos)
    pbv = np.array([-0.1, 0.5, -0.2])
    
    rgb = np.zeros((n_samples, 3))
    for i in range(n_samples):
        # Modulate light multiplicatively, pulse additively to skin color
        current_light = 1 + light[i]
        rgb[i] = skin_dc * current_light + pbv * pulse[i]
        
    # Add independent white noise
    rgb += np.random.randn(n_samples, 3) * noise_amp
    return rgb

def method_a(rgb1, rgb2, rgb3, fs):
    # Method A: POS -> Detrend -> Bandpass -> Pearson
    pos = POSMethod(fps=fs)
    
    def process_roi(rgb):
        if np.mean(rgb) == 0:
            return np.zeros(len(rgb))
        p = pos.process(rgb) # process already detrends and bandpasses
        return p

    start = time.perf_counter()
    p1 = process_roi(rgb1)
    p2 = process_roi(rgb2)
    p3 = process_roi(rgb3)
    
    r12 = np.corrcoef(p1, p2)[0,1] if np.std(p1)>0 and np.std(p2)>0 else 0
    r13 = np.corrcoef(p1, p3)[0,1] if np.std(p1)>0 and np.std(p3)>0 else 0
    r23 = np.corrcoef(p2, p3)[0,1] if np.std(p2)>0 and np.std(p3)>0 else 0
    cost = time.perf_counter() - start
    return r12, r13, r23, cost

def method_b(rgb1, rgb2, rgb3, fs):
    # Method B: Green detrend -> Bandpass -> Pearson
    def process_roi(rgb):
        g = rgb[:, 1]
        if np.mean(g) == 0:
            return np.zeros(len(g))
        g = signal.detrend(g)
        g = butter_bandpass_filter(g, 0.75, 2.50, fs, order=1)
        return g

    start = time.perf_counter()
    p1 = process_roi(rgb1)
    p2 = process_roi(rgb2)
    p3 = process_roi(rgb3)
    
    r12 = np.corrcoef(p1, p2)[0,1] if np.std(p1)>0 and np.std(p2)>0 else 0
    r13 = np.corrcoef(p1, p3)[0,1] if np.std(p1)>0 and np.std(p3)>0 else 0
    r23 = np.corrcoef(p2, p3)[0,1] if np.std(p2)>0 and np.std(p3)>0 else 0
    cost = time.perf_counter() - start
    return r12, r13, r23, cost

def run_experiment():
    np.random.seed(42)
    n_samples = 240
    fs = 30.0
    N_trials = 100
    
    print("Running Method A vs Method B Benchmark...", flush=True)
    print("A: POS -> Detrend -> Bandpass -> Pearson", flush=True)
    print("B: Green detrend -> Bandpass -> Pearson\n", flush=True)
    
    scenarios = {
        "1. Independent Noise (r~0)": {"pulse_amp": 0.0, "light_amp": 0.0, "noise_amp": 5.0},
        "2. Shared Light Variation (No Pulse)": {"pulse_amp": 0.0, "light_amp": 0.1, "noise_amp": 1.0},
        "3. Shared Real Pulse + Noise": {"pulse_amp": 2.0, "light_amp": 0.0, "noise_amp": 1.0},
        "4. Pulse + Light + Noise": {"pulse_amp": 2.0, "light_amp": 0.05, "noise_amp": 1.0},
    }
    
    for name, params in scenarios.items():
        rA_list = []
        rB_list = []
        cost_A = 0
        cost_B = 0
        for _ in range(N_trials):
            rgb1 = synthesize_rgb(n_samples, fs, **params)
            rgb2 = synthesize_rgb(n_samples, fs, **params)
            rgb3 = synthesize_rgb(n_samples, fs, **params)
            
            r12A, r13A, r23A, cA = method_a(rgb1, rgb2, rgb3, fs)
            r12B, r13B, r23B, cB = method_b(rgb1, rgb2, rgb3, fs)
            
            rA_list.extend([r12A, r13A, r23A])
            rB_list.extend([r12B, r13B, r23B])
            cost_A += cA
            cost_B += cB
            
        print(f"Scenario: {name}", flush=True)
        print(f"  Method A (POS)   - Mean r: {np.mean(rA_list):.3f}, 95th: {np.percentile(rA_list, 95):.3f}", flush=True)
        print(f"  Method B (Green) - Mean r: {np.mean(rB_list):.3f}, 95th: {np.percentile(rB_list, 95):.3f}", flush=True)
        print(f"  Time (per 3-ROI calc) -> A: {cost_A/N_trials*1000:.2f} ms | B: {cost_B/N_trials*1000:.2f} ms\n", flush=True)

if __name__ == "__main__":
    run_experiment()
