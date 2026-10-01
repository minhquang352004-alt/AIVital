import numpy as np
import pytest
from aivitals_engine.quality.sqi import calculate_cross_roi_sqi

def synthesize_rgb(n_samples, fs, pulse_amp=0.01, light_amp=0.0, noise_amp=0.01):
    t = np.arange(n_samples) / fs
    pulse = pulse_amp * np.sin(2 * np.pi * 1.2 * t)
    light = light_amp * np.sin(2 * np.pi * 0.5 * t)
    skin_dc = np.array([120, 80, 70])
    pbv = np.array([-0.1, 0.5, -0.2])
    
    rgb = np.zeros((n_samples, 3))
    for i in range(n_samples):
        current_light = 1 + light[i]
        rgb[i] = skin_dc * current_light + pbv * pulse[i]
        
    rgb += np.random.randn(n_samples, 3) * noise_amp
    return rgb

def test_cross_roi_sqi_independent_noise():
    np.random.seed(42)
    fs = 30.0
    n_samples = 240
    
    # Independent noise only
    sub_rgbs = {
        'forehead': synthesize_rgb(n_samples, fs, pulse_amp=0, light_amp=0, noise_amp=5.0),
        'left_cheek': synthesize_rgb(n_samples, fs, pulse_amp=0, light_amp=0, noise_amp=5.0),
        'right_cheek': synthesize_rgb(n_samples, fs, pulse_amp=0, light_amp=0, noise_amp=5.0),
    }
    
    res = calculate_cross_roi_sqi(sub_rgbs, fs)
    assert abs(res['r_mean']) < 0.4
    assert abs(res['r_min']) < 0.4

def test_cross_roi_sqi_shared_pulse():
    np.random.seed(42)
    fs = 30.0
    n_samples = 240
    
    # Shared real pulse + noise
    sub_rgbs = {
        'forehead': synthesize_rgb(n_samples, fs, pulse_amp=2.0, light_amp=0, noise_amp=1.0),
        'left_cheek': synthesize_rgb(n_samples, fs, pulse_amp=2.0, light_amp=0, noise_amp=1.0),
        'right_cheek': synthesize_rgb(n_samples, fs, pulse_amp=2.0, light_amp=0, noise_amp=1.0),
    }
    
    res = calculate_cross_roi_sqi(sub_rgbs, fs)
    assert res['r_mean'] > 0.7
    assert res['r_min'] > 0.6

def test_cross_roi_sqi_one_region_noise():
    np.random.seed(42)
    fs = 30.0
    n_samples = 240
    
    # 2 ROIs good, 1 ROI noisy
    sub_rgbs = {
        'forehead': synthesize_rgb(n_samples, fs, pulse_amp=2.0, light_amp=0, noise_amp=1.0),
        'left_cheek': synthesize_rgb(n_samples, fs, pulse_amp=2.0, light_amp=0, noise_amp=1.0),
        'right_cheek': synthesize_rgb(n_samples, fs, pulse_amp=0.0, light_amp=0, noise_amp=5.0), # NOISE
    }
    
    res = calculate_cross_roi_sqi(sub_rgbs, fs)
    # Forehead-Left should be high
    assert res['r_forehead_left'] > 0.7
    # Forehead-Right and Left-Right should be low
    assert abs(res['r_forehead_right']) < 0.3
    assert abs(res['r_left_right']) < 0.3
    # Min is low
    assert res['r_min'] < 0.3

def test_cross_roi_sqi_shared_noise_limit():
    np.random.seed(42)
    fs = 30.0
    n_samples = 240
    
    # Shared noise that mimics pulse frequency (1.2 Hz) across all 3 ROIs
    # This proves the limitation: Cross-ROI SQI is TRICKED by shared noise in the heart rate band
    fake_pulse_noise = synthesize_rgb(n_samples, fs, pulse_amp=2.0, light_amp=0, noise_amp=0.0)
    
    sub_rgbs = {
        'forehead': fake_pulse_noise + np.random.randn(n_samples, 3) * 0.1,
        'left_cheek': fake_pulse_noise + np.random.randn(n_samples, 3) * 0.1,
        'right_cheek': fake_pulse_noise + np.random.randn(n_samples, 3) * 0.1,
    }
    
    res = calculate_cross_roi_sqi(sub_rgbs, fs)
    # the fake noise is identical, so r is very high
    assert res['r_mean'] > 0.9
    # XÁC NHẬN: Đây là giới hạn. Chỉ số này ĐÁNH LỪA được nếu có nhiễu tuần hoàn chung trên cả 3 vùng.
