import numpy as np
from aivitals_engine.quality.motion import calculate_motion_sqi

def test_motion_sqi_static():
    # Không chuyển động
    bboxes = np.tile([100, 100, 50, 50], (240, 1))
    res = calculate_motion_sqi(bboxes, 30.0)
    assert res['motion_score'] == 0.0
    assert res['raw_variance'] == 0.0

def test_motion_sqi_rhythmic():
    # Chuyển động tuần hoàn (1.2 Hz)
    t = np.arange(240) / 30.0
    cx = 100 + 10 * np.sin(2 * np.pi * 1.2 * t)
    bboxes = np.zeros((240, 4))
    bboxes[:, 0] = cx - 25
    bboxes[:, 1] = 100
    bboxes[:, 2] = 50
    bboxes[:, 3] = 50
    
    res = calculate_motion_sqi(bboxes, 30.0)
    # Vì tất cả chuyển động là tuần hoàn trong dải tim, ratio phải rất cao (> 0.9)
    assert res['motion_score'] > 0.9
    assert res['raw_variance'] > 0

def test_motion_sqi_random_walk():
    # Chuyển động ngẫu nhiên (chủ yếu là tần số thấp, ngoài dải tim)
    np.random.seed(42)
    vx = np.random.randn(240) * 2
    cx = 100 + np.cumsum(vx)
    bboxes = np.zeros((240, 4))
    bboxes[:, 0] = cx - 25
    bboxes[:, 1] = 100
    bboxes[:, 2] = 50
    bboxes[:, 3] = 50
    
    res = calculate_motion_sqi(bboxes, 30.0)
    # Tỷ lệ năng lượng trong dải tim (bandpass) so với random walk (năng lượng dồn ở tần số thấp) phải thấp
    assert res['motion_score'] < 0.4
    assert res['raw_variance'] > 0
