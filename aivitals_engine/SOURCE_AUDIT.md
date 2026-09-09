# SOURCE AUDIT: rPPG-Toolbox for AIVitals Pipeline

> **Dự án:** AIVitals (Hệ thống đo sinh hiệu không tiếp xúc qua Camera)  
> **Tài liệu:** Khảo sát & Đánh giá mã nguồn [`ubicomplab/rPPG-Toolbox`](https://github.com/ubicomplab/rPPG-Toolbox)  
> **Đối tượng:** Toàn bộ Team Kỹ thuật (Signal, AI Model, Backend, Frontend)

---

## 1. MỤC TIÊU & PHẠM VI AUDIT

Tài liệu này đánh giá toàn diện repository mã nguồn mở `rPPG-Toolbox` nhằm:
1. Xác định danh mục các thuật toán (Toán học / Unsupervised & Học sâu / Deep Models).
2. Chuẩn hóa đặc tả dữ liệu đầu vào (Input) và đầu ra (Output) của từng module.
3. Thống kê phiên bản Python và các thư viện phụ thuộc (Dependencies).
4. Phân loại mức độ sử dụng cho hệ thống AIVitals: **REUSE**, **ADAPTER**, **RESEARCH ONLY**, **NOT USABLE**.
5. Nhận diện các rủi ro pháp lý (License) và nút thắt kỹ thuật (Technical Bottlenecks).
6. Làm rõ các khoảng trống tính năng (Functional Gaps) so với mục tiêu đo **HR/HRV/RR** của dự án.

---

## 2. MÔI TRƯỜNG & THƯ VIỆN (DEPENDENCIES)

* **Python Runtime:** Python **3.8** (xác định theo `setup.sh`).
* **Phân nhóm Dependencies trong Repo:**

| Nhóm | Thư viện chính | Đánh giá sử dụng cho Team |
| :--- | :--- | :--- |
| **Core Signal (Nhẹ)** | `numpy==1.22.0`, `scipy==1.5.2`, `opencv-python==4.5.2.54` | **Bắt buộc cho V1**. Đủ để chạy toàn bộ pipeline POS, CHROM, GREEN, Detrend, FFT và SNR mà không cần GPU. |
| **Deep Learning (Rất nặng)** | `torch==2.1.2+cu121`, `torchvision==0.16.2`, `timm==1.0.11`, `mamba-ssm==2.2.2`, `causal-conv1d==1.0.0` | **Chưa dùng cho V1 (Dành cho V2)**. Cần GPU và trình biên dịch CUDA C++, loại bỏ khỏi pipeline MVP để tối ưu tài nguyên CPU. |
| **Training & Parsing Framework** | `yacs==0.1.8`, `PyYAML==6.0`, `h5py==2.10.0`, `mat73==0.59`, `tensorboardX==2.4.1` | **Không sử dụng trong Production**. Chỉ phục vụ huấn luyện và đọc dataset offline của repo gốc. |

---

## 3. BẢNG PHÂN LOẠI MÃ NGUỒN (SOURCE AUDIT MATRIX)

Đánh giá các module trong thư mục `rPPG-Toolbox/` theo đường dẫn tương đối:

| Module / File nguồn | Phân loại | Chức năng chính | Hướng giải quyết cho Team |
| :--- | :---: | :--- | :--- |
| `unsupervised_methods/methods/POS_WANG.py` | **REUSE** | Thuật toán POS (Plane-Orthogonal-to-Skin) | Tái sử dụng công thức toán cốt lõi. Tuy nhiên **KHÔNG** thể gọi thẳng frame-by-frame — xem mục 6.5. |
| `unsupervised_methods/methods/CHROME_DEHAAN.py` | **REUSE** | Thuật toán CHROM (Chrominance-based) | Tái sử dụng phép chiếu sắc độ Xs, Ys và lọc bandpass. Cần wrapper sliding window — xem mục 6.5. |
| `unsupervised_methods/methods/GREEN.py` | **REUSE** | Thuật toán trích xuất kênh Green | Tái sử dụng trực tiếp làm baseline (rất nhẹ). Cần wrapper sliding window. |
| `unsupervised_methods/utils.py` | **REUSE** | Khử trôi xu hướng `detrend()` | Tái sử dụng nguyên vẹn thuật toán Smoothness Priors Detrending. |
| `evaluation/post_process.py` — `_calculate_fft_hr`, `_calculate_peak_hr` | **REUSE** | Tính HR (FFT / Peak) | Tái sử dụng. Không phụ thuộc ground-truth ở runtime. |
| `evaluation/post_process.py` — `_calculate_SNR` | **ADAPTER** | Tính SNR | Hàm gốc nhận `hr_label` là ground-truth HR (BPM từ ECG/PPG chuẩn). **KHÔNG phải SQI độc lập.** Cần viết lại để tự suy f0 từ phổ tín hiệu ước tính — xem mục 6.3. |
| `dataset/data_loader/BaseLoader.py` | **ADAPTER** | Phát hiện mặt và cắt ROI (`face_detection`) | Không kế thừa class này. Viết module bọc ngoài độc lập (khuyến nghị dùng MediaPipe Face Mesh thay cho Haar Cascade). |
| `unsupervised_methods/methods/PBV.py` | **RESEARCH ONLY** | Thuật toán PBV (Blood Volume Pulse Signature) | Giữ lại đối chuẩn so sánh; nhạy cảm với sai lệch cảm biến màu camera. |
| `unsupervised_methods/methods/LGI.py` | **RESEARCH ONLY** | Thuật toán LGI (Local Group Invariance) | Dùng phân rã SVD từng block; tính toán phức tạp hơn POS nhưng độ chính xác không vượt trội. |
| `unsupervised_methods/methods/OMIT.py` | **RESEARCH ONLY** | Thuật toán OMIT (QR Decomposition) | Dùng phân rã ma trận trực giao QR; giữ lại phục vụ nghiên cứu so sánh. |
| `unsupervised_methods/methods/ICA_POH.py` | **NOT USABLE** | Phân tách nguồn mù ICA (JADE) | Ngốn CPU, độ trễ lớn, thứ tự kênh trích xuất bị ngẫu nhiên; không dùng cho realtime. |
| `neural_methods/model/*` | **RESEARCH / V2** | Các mô hình Deep Learning (PhysNet, DeepPhys...) | Lưu trữ tham khảo kiến trúc và interface cho giai đoạn V2. |
| `dataset/data_loader/*.py` | **NOT USABLE** | Dataloader offline (UBFC, PURE, SCAMPS...) | Phục vụ đọc file video từ đĩa cho PyTorch batching, không dùng cho luồng camera realtime. |
| `tools/preprocessing_viz/`, `tools/output_signal_viz/` | **NOT USABLE** | Notebook visualize data train/test | Phụ thuộc định dạng file cache nội bộ (`.npy`, `.pickle`). |

---

## 4. ĐẶC TẢ CHI TIẾT THUẬT TOÁN UNSUPERVISED (SIGNAL CORE)

Tất cả các hàm trong repo gốc nhận đầu vào là mảng video frames `(T, H, W, 3)` và trả về chuỗi 1D tín hiệu BVP. **Quan trọng: Bước spatial averaging (tính trung bình pixel toàn frame) được thực hiện BÊN TRONG mỗi hàm** — không phải nhận RGB buffer sẵn — chi tiết chính xác xem mục 4.A.

### 4.1. POS (Plane-Orthogonal-to-Skin)
* **File nguồn:** `unsupervised_methods/methods/POS_WANG.py` (Wang et al., IEEE TBME 2017)
* **Input thực tế:** `frames` shape `(T, H, W, 3)`, `fs` (Hz).
* **Output:** BVP 1D shape `(T,)` — đã được khử trôi (detrend λ=100) và lọc Bandpass Butterworth bậc 1 [0.75, 3.0] Hz. **Output KHÔNG chuẩn hóa zero-mean/unit-variance** — biên độ vật lý giữ nguyên sau detrend+filter.
* **Logic toán học cốt lõi:**
  1. Cửa sổ thời gian trượt `l = ceil(1.6 × fs)` (tương đương 1.6 giây).
  2. Chuẩn hóa RGB từng khung theo giá trị trung bình trong cửa sổ: `Cn = RGB[m:n] / mean(RGB[m:n])`.
  3. Chiếu tín hiệu lên mặt phẳng trực giao với vector sắc da: `S = [[0, 1, -1], [-2, 1, 1]] @ Cn.T`
  4. Kết hợp thích ứng: `h = S[0] + (std(S[0]) / std(S[1])) * S[1]`, sau đó trừ mean và cộng dồn tích lũy vào buffer tín hiệu H.
  5. Hậu xử lý: Khử trôi bằng Smoothness Priors Detrending (λ = 100) và lọc Bandpass Butterworth bậc 1 [0.75, 3.0] Hz (45–180 bpm).
* **Đánh giá:** Thuật toán **chính xác và bền vững nhất** nhóm unsupervised, chịu rung lắc mặt tốt.

### 4.2. CHROM (Chrominance-based rPPG)
* **File nguồn:** `unsupervised_methods/methods/CHROME_DEHAAN.py` (De Haan & Jeanne, IEEE TBME 2013)
* **Input thực tế:** `frames` shape `(T, H, W, 3)`, `FS` (Hz).
* **Output:** BVP 1D shape biến thiên (xấp xỉ T, phụ thuộc cách ghép cửa sổ overlap-add) — **KHÔNG chuẩn hóa**, biên độ giữ nguyên sau tích hợp cửa sổ.
* **Logic toán học cốt lõi:**
  1. Sử dụng cửa sổ 1.6s, chồng chập 50% (Overlap-add).
  2. Chuẩn hóa `RGB_norm = RGB / mean(RGB)`.
  3. Tạo 2 tín hiệu sắc độ trực giao với hướng phản xạ gương: `Xs = 3*R_norm - 2*G_norm`, `Ys = 1.5*R_norm + G_norm - 1.5*B_norm`
  4. Lọc dải thông Butterworth bậc 3 [0.7, 2.5] Hz thu được Xf, Yf.
  5. Tính `alpha = std(Xf) / std(Yf)` và kết hợp: `S = (Xf - alpha*Yf) * Hanning`.
* **Đánh giá:** Triệt tiêu biến thiên ánh sáng môi trường rất tốt, tốc độ tính toán nhanh.

### 4.3. GREEN
* **File nguồn:** `unsupervised_methods/methods/GREEN.py` (Verkruysse et al., Optics Express 2008)
* **Input thực tế:** `frames` shape `(T, H, W, 3)` — bên trong gọi `utils.process_video(frames)`.
* **Output:** BVP 1D shape `(T,)` — **KHÔNG chuẩn hóa**, là giá trị trung bình pixel kênh xanh lá thô.
* **Logic:** Lấy trực tiếp kênh xanh lá `BVP(t) = RGB_G(t)`. Rất nhẹ nhưng kém bền vững trước chuyển động.

### 4.4. Các thuật toán còn lại (PBV, LGI, OMIT, ICA)
* **PBV (`PBV.py`):** Input `frames` `(T,H,W,3)` — gọi `utils.process_video()`. Output shape `(T,)`. Dựa trên vector chữ ký xung chuẩn Pbv của máu, giải hệ phương trình hiệp phương sai `Q·W = Pbv`. Nhạy cảm nếu camera bị méo màu.
* **LGI (`LGI.py`):** Input `frames` `(T,H,W,3)` — gọi `utils.process_video()`. Output shape `(T,)`. Dùng phân rã SVD để chiếu tín hiệu lên không gian bất biến nhóm `P = I - S·S^T`.
* **OMIT (`OMIT.py`):** Input `frames` `(T,H,W,3)` — gọi `utils.process_video()`. Output shape `(T,)`. Dùng phân rã ma trận trực giao QR.
* **ICA (`ICA_POH.py`):** Input `frames` `(T,H,W,3)`, `FS` (Hz). Output shape `(T,)`. Dùng thuật toán JADE phân tách nguồn mù. Tốn tài nguyên, không kiểm soát được thứ tự kênh đầu ra.

---

## 4.A. BẢNG "FUNCTION SIGNATURE SPEC" — CHỮ KÝ HÀM CHÍNH XÁC TỪ SOURCE

> **Đọc từ source thật ngày 2026-09-08. Không suy luận.**

### Các hàm thuật toán unsupervised

| Hàm | Chữ ký hàm thật trong source | Input thực nhận | `fs` — nguồn gốc | Output: shape & chuẩn hóa |
| :--- | :--- | :--- | :--- | :--- |
| `POS_WANG` | `def POS_WANG(frames, fs)` | `frames`: numpy array `(T,H,W,3)` — thô từ video/camera. Bên trong tự làm spatial avg qua `_process_video(frames)` → `RGB (T,3)`. | `fs`: argument tường minh (float/int). Lấy từ `config.UNSUPERVISED.DATA.FS` trong YAML (ví dụ: `FS: 30` cho UBFC-rPPG). **KHÔNG hard-code bên trong hàm.** | `BVP`: numpy 1D `(T,)`. **Không** chuẩn hóa zero-mean/unit-variance. Biên độ thực sau detrend + bandpass. |
| `CHROME_DEHAAN` | `def CHROME_DEHAAN(frames, FS)` | `frames`: numpy array `(T,H,W,3)`. Bên trong tự làm spatial avg qua `process_video(frames)` → `RGB (T,3)`. | `FS`: argument tường minh (float/int). Lấy từ config/dataset metadata. | `BVP` (tên `S` trong code): numpy 1D, độ dài ≈ `T` (phụ thuộc overlap-add). **Không** chuẩn hóa. |
| `GREEN` | `def GREEN(frames)` | `frames`: numpy array `(T,H,W,3)`. Bên trong gọi `utils.process_video(frames)` → shape `(1,3,T)`. | **Không có tham số `fs`** — hàm không dùng sampling rate. | `BVP`: numpy 1D `(T,)`. Là giá trị trung bình pixel kênh G thô — **không** chuẩn hóa. |
| `PBV` | `def PBV(frames)` | `frames`: numpy array `(T,H,W,3)`. Bên trong gọi `utils.process_video(frames)` → shape `(1,3,T)`. | **Không có tham số `fs`.** | `bvp`: numpy 1D `(T,)`. **Không** chuẩn hóa. |
| `LGI` | `def LGI(frames)` | `frames`: numpy array `(T,H,W,3)`. Bên trong gọi `utils.process_video(frames)` → shape `(1,3,T)`. | **Không có tham số `fs`.** | `bvp`: numpy 1D `(T,)`. **Không** chuẩn hóa. |
| `OMIT` | `def OMIT(frames)` | `frames`: numpy array `(T,H,W,3)`. Bên trong gọi `utils.process_video(frames)`. | **Không có tham số `fs`.** | `bvp`: numpy 1D `(T,)`. **Không** chuẩn hóa. |
| `ICA_POH` | `def ICA_POH(frames, FS)` | `frames`: numpy array `(T,H,W,3)`. Bên trong tự làm spatial avg qua `process_video(frames)` → `RGB (T,3)`. ICA sau đó chuẩn hóa nội bộ mỗi kênh: `(detrend - mean) / std`. | `FS`: argument tường minh (float/int). Lấy từ config. | `BVP`: numpy 1D `(T,)`. Output đã qua ICA + bandpass — biên độ thực sau filter. |

### Hàm tiện ích

| Hàm | Chữ ký hàm thật trong source | Input | Output & ghi chú |
| :--- | :--- | :--- | :--- |
| `utils.detrend` | `def detrend(input_signal, lambda_value)` | `input_signal`: numpy array `(N,)` hoặc matrix. `lambda_value`: float (thường = 100). | Numpy array cùng shape — tín hiệu sau khử trôi Smoothness Priors. **Không** chuẩn hóa biên độ. |
| `utils.process_video` | `def process_video(frames)` | `frames`: numpy array `(T,H,W,3)`. | numpy array shape `(1, 3, T)` — spatial average toàn frame theo từng kênh màu. **Đây là bước tách riêng** so với `_process_video` trong POS và CHROME — các hàm đó có `_process_video` / `process_video` nội bộ riêng trả về `(T,3)`. |

### Hàm hậu xử lý (post_process.py)

| Hàm | Chữ ký hàm thật trong source | Input | Output & ghi chú |
| :--- | :--- | :--- | :--- |
| `_calculate_fft_hr` | `def _calculate_fft_hr(ppg_signal, fs=60, low_pass=0.6, high_pass=3.3)` | `ppg_signal`: numpy 1D. `fs`: float (default 60 — chú ý default cao, cần truyền đúng fs thực). `low_pass`, `high_pass`: Hz. | `fft_hr`: float (BPM). Tự suy ra từ đỉnh phổ — **không cần ground-truth.** |
| `_calculate_peak_hr` | `def _calculate_peak_hr(ppg_signal, fs)` | `ppg_signal`: numpy 1D. `fs`: float (bắt buộc truyền). | `hr_peak`: float (BPM). Tự suy từ khoảng cách đỉnh — **không cần ground-truth.** |
| `_calculate_SNR` | `def _calculate_SNR(pred_ppg_signal, hr_label, fs=30, low_pass=0.6, high_pass=3.3)` | `pred_ppg_signal`: numpy 1D — tín hiệu BVP ước tính. **`hr_label`: float (BPM) — nhịp tim ground-truth từ ECG/PPG chuẩn, KHÔNG phải từ phổ tín hiệu ước tính.** `fs`: float. `low_pass`, `high_pass`: Hz. | `SNR`: float (dB). Chi tiết: xem mục 6.3. |

> **Lưu ý quan trọng về `process_video`:**
> `utils.process_video(frames)` trả về shape `(1, 3, T)` — reshape khác với `_process_video()` nội bộ trong POS/CHROME/ICA trả về `(T, 3)`. Không hoán đổi lẫn nhau. Team cần hiểu rõ từng hàm gọi cái nào.

> **Lưu ý về fs trong YAML config:**
> File `configs/infer_configs/UBFC-rPPG_UNSUPERVISED.yaml` khai báo `FS: 30` dưới key `UNSUPERVISED.DATA.FS`. Giá trị này được truyền tường minh vào hàm qua `config.UNSUPERVISED.DATA.FS` — **không hard-code trong thuật toán**. Ở AIVitals, `fs` phải đến từ timestamp thực tế của camera (xem mục 8.3).

---

## 5. ĐẶC TẢ GIAO DIỆN CÁC MÔ HÌNH DEEP LEARNING (ĐỊNH HƯỚNG V2)

Bảng tổng hợp đặc tả Input/Output của các mạng nơ-ron trong thư mục `neural_methods/model/`:

| Tên Model | File nguồn | Kích thước Frame & Window | Định dạng Input | Định dạng Output | Yêu cầu phần cứng |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **DeepPhys** | `DeepPhys.py` | H=W=36, Cặp 2 frame liên tiếp | (B, 3, H, W) x2 (Frame vi sai chuẩn hóa + Frame gốc) | 1 giá trị vi sai nhịp tim tức thời dBVP/dt trên mỗi frame | CPU / Edge GPU (Rất nhẹ, chạy realtime tốt) |
| **TS-CAN** | `TS_CAN.py` | H=W=36 hoặc 72, Window 10~20 frames | Cặp tensor (B, T, 3, H, W) | Đa nhiệm: Tín hiệu nhịp tim (dBVP) + Tín hiệu nhịp thở (Resp) | GPU / NPU |
| **PhysNet** | `PhysNet.py` | H=W=72, Window 64~128 frames (2-4s) | Tensor 5D: (B, 3, T, H, W) | Chuỗi sóng BVP liên tục độ dài T | Bắt buộc GPU (nặng) |
| **EfficientPhys** | `EfficientPhys.py` | H=W=72, Window 64 frames | Tensor: (B, 3, T, H, W) | Chuỗi sóng BVP độ dài T | Tối ưu cho Mobile / Edge Device |
| **PhysFormer** | `PhysFormer.py` | H=W=160, Window 160 frames | Tensor: (B, 3, T, H, W) | Chuỗi sóng BVP độ dài T | GPU hiệu năng cao |
| **PhysMamba** | `PhysMamba.py` | H=W=72, Window 160 frames | Tensor: (B, 3, T, H, W) | Chuỗi sóng BVP độ dài T | GPU hỗ trợ CUDA (thư viện `mamba-ssm`) |

---

## 6. TIỀN XỬ LÝ, HẬU XỬ LÝ & CHỈ SỐ CHẤT LƯỢNG (SQI)

### 6.1. Khử trôi xu hướng (Detrending)
* **File nguồn:** `unsupervised_methods/utils.py`
* **Hàm:** `detrend(input_signal, lambda_value)` — xem chữ ký chính xác ở mục 4.A.
* Sử dụng thuật toán **Smoothness Priors Detrending** (Tarvainen et al.). Giải hệ phương trình ma trận thưa bậc hai để triệt tiêu dao động tần số thấp (trôi đường đẳng điện do nhịp thở hoặc biến thiên ánh sáng chậm). Tái sử dụng nguyên vẹn hàm này.

### 6.2. Ước lượng nhịp tim (Heart Rate Estimation)
Trong `evaluation/post_process.py`, repo cung cấp 2 phương pháp — **cả hai đều tự suy ra HR từ phổ tín hiệu ước tính, không cần ground-truth:**
1. **Qua biến đổi Fourier (`_calculate_fft_hr` — Khuyên dùng):**
   * Chữ ký: `_calculate_fft_hr(ppg_signal, fs=60, low_pass=0.6, high_pass=3.3)`
   * ⚠️ Default `fs=60` — phải truyền đúng `fs` thực của camera.
   * Đệm 0 (Zero-padding) đến lũy thừa 2 gần nhất để tăng độ mịn của phổ.
   * Tính Periodogram bằng `scipy.signal.periodogram` trong dải sinh lý [0.75, 2.5] Hz (45–150 bpm).
   * Xác định tần số đỉnh cực đại: `HR_FFT = f_peak × 60`.
2. **Qua phát hiện đỉnh sóng (`_calculate_peak_hr`):**
   * Chữ ký: `_calculate_peak_hr(ppg_signal, fs)`
   * Dùng `scipy.signal.find_peaks` tìm các đỉnh tâm thu.
   * Tính khoảng cách đỉnh liên tiếp (IBI): `HR_Peak = 60 / mean(Δt)`.

### 6.3. Chỉ số chất lượng tín hiệu (Signal Quality Index — SQI) ⚠️ ĐÃ SỬA

> **[SỬA LỖI PHÂN TÍCH QUAN TRỌNG — v1.3]**

#### Xác nhận từ source thật (`evaluation/post_process.py`, dòng 78–131):

```python
def _calculate_SNR(pred_ppg_signal, hr_label, fs=30, low_pass=0.6, high_pass=3.3):
    # Get the first and second harmonics of the ground truth HR in Hz
    first_harmonic_freq = hr_label / 60          # <-- f0 = GROUND-TRUTH HR
    second_harmonic_freq = 2 * first_harmonic_freq
    deviation = 6 / 60  # 6 beats/min = 0.1 Hz
    ...
    SNR = power2db((signal_power_hm1 + signal_power_hm2) / signal_power_rem)
    return SNR
```

**Kết luận xác nhận:**

* Tham số `hr_label` (BPM) **là ground-truth HR từ ECG hoặc PPG reference** — được tính từ `labels_input` (tín hiệu nhãn thật của dataset) ở `unsupervised_predictor.py` dòng 162:
  ```python
  SNR = _calculate_SNR(predictions, hr_label, fs=fs)
  # hr_label = _calculate_fft_hr(labels, fs=fs)  ← từ labels ECG/PPG chuẩn
  ```
* **f0 KHÔNG lấy từ phổ tín hiệu ước tính (`pred_ppg_signal`) mà lấy từ ground-truth `hr_label`.**

#### Hệ quả kiến trúc cho AIVitals:

1. **Hàm SNR gốc là METRIC ĐÁNH GIÁ OFFLINE** — dùng để so sánh chất lượng tín hiệu ước tính với nhãn thật, **không phải SQI real-time độc lập**. Không thể gọi thẳng ở runtime vì không có `hr_label` ground-truth.

2. **Cần viết lại cho runtime:** Để có SQI thực sự độc lập tại runtime, phải thay `hr_label` bằng HR tự suy từ phổ tín hiệu ước tính:
   ```python
   # Phiên bản AIVitals runtime (self-supervised SNR):
   hr_estimated = _calculate_fft_hr(pred_ppg_signal, fs=fs)
   snr = _calculate_SNR(pred_ppg_signal, hr_label=hr_estimated, fs=fs)
   ```

3. **Rủi ro của SNR "tự suy" (self-supervised SNR):**
   * Nếu tín hiệu kém chất lượng, `_calculate_fft_hr` sẽ chọn sai đỉnh phổ → f0 sai → SNR tính quanh sai tần số → **SNR cao giả tạo dù tín hiệu thực ra rất tệ**.
   * SNR so-với-label đáng tin hơn vì f0 đến từ nguồn độc lập (ECG/PPG chuẩn).

4. **Khuyến nghị fallback bổ sung** để bù cho độ kém tin cậy của SNR tự suy:
   * **Periodicity check:** Tính autocorrelation tín hiệu BVP — tín hiệu tuần hoàn tốt sẽ có đỉnh autocorr rõ tại lag = 1/HR.
   * **Cross-ROI consistency:** So sánh HR ước tính từ vùng trán và vùng má — nếu sai lệch > 5 bpm → báo chất lượng thấp.
   * **Spectral flatness check:** Tính spectral entropy trong dải [0.6, 3.3] Hz — tín hiệu nhiễu trắng có entropy cao, BVP tốt có entropy thấp.

#### Công thức SNR gốc (vẫn dùng cho đánh giá offline):
1. `f0 = hr_label / 60` Hz (ground-truth), `f1 = 2*f0` (họa âm bậc 2).
2. Đặt khoảng dung sai `Δf = 6/60 = 0.1` Hz (±6 bpm).
3. **Công suất tín hiệu (P_signal):** Diện tích phổ trong `[f0 ± Δf] ∪ [f1 ± Δf]`.
4. **Công suất nhiễu (P_noise):** Diện tích phổ còn lại trong dải [0.6, 3.3] Hz.
5. `SNR (dB) = 10 * log10(P_signal / P_noise)`.
6. **Chuẩn hóa SQI (0.0 → 1.0) — cần AIVitals tự viết:**
   `SQI = Clip((SNR - SNR_min) / (SNR_max - SNR_min), 0.0, 1.0)`
   *(Cấu hình khuyến nghị: SNR_min = -5 dB, SNR_max = 10 dB. Nếu SQI < 0.4 → Cảnh báo tín hiệu kém).*

### 6.4. ⚠️ CẢNH BÁO THỨ TỰ KÊNH MÀU: RGB vs BGR

**Xác nhận từ source:**
* `BaseLoader.py` đọc video bằng `cv2` (OpenCV), `cv2.VideoCapture` mặc định trả về frame theo thứ tự **BGR** (Blue-Green-Red).
* `crop_face_resize()` dòng 404 dùng `cv2.resize(frame, ...)` — frame vẫn giữ thứ tự BGR.
* Các hàm `POS_WANG`, `CHROME_DEHAAN` lấy kênh theo chỉ số `[:, 0]`, `[:, 1]`, `[:, 2]` — giả định **kênh 0 = R, kênh 1 = G, kênh 2 = B**.

**Công thức CHROM phụ thuộc thứ tự kênh:**

```
Xs = 3 * RGBNorm[:, 0] - 2 * RGBNorm[:, 1]       # 3R - 2G
Ys = 1.5 * RGBNorm[:, 0] + RGBNorm[:, 1] - 1.5 * RGBNorm[:, 2]  # 1.5R + G - 1.5B
```

**Nếu nhầm BGR → RGB:** Xs sẽ là `3B - 2G` thay vì `3R - 2G` → kết quả hoàn toàn sai nhưng **không có exception nào được báo**, rất khó debug.

**Yêu cầu bắt buộc cho AIVitals:**
* Module Face/ROI của AIVitals sau khi trích xuất pixel từ camera **PHẢI convert sang RGB trước khi tạo rgb_buffer `(N,3)`**:
  ```python
  frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
  # Hoặc: frame_rgb = frame_bgr[:, :, ::-1]
  ```
* Thêm assert kiểm tra khi debug:
  ```python
  assert rgb_buffer.shape[1] == 3, "Expected (N,3) RGB buffer"
  # Kênh đỏ (R) trung bình thường > kênh xanh lam (B) cho da người
  ```

### 6.5. ⚠️ MISMATCH BATCH/OFFLINE vs STREAMING update()

**Xác nhận từ source (`unsupervised_predictor.py` dòng 28–46):**
```python
for idx in range(batch_size):
    data_input = test_batch[0][idx].cpu().numpy()  # shape: (T, H, W, 3) - TOÀN BỘ video
    BVP = POS_WANG(data_input, config.UNSUPERVISED.DATA.FS)  # xử lý cả video 1 lần
```

**Kết luận:**
* `POS_WANG`, `CHROME_DEHAAN`, `GREEN`, `PBV`, `LGI`, `OMIT` — **tất cả đều nhận toàn bộ mảng frames một lần duy nhất** và trả về toàn bộ tín hiệu BVP.
* **Không có state nội bộ** giữa các lần gọi — mỗi lần gọi là độc lập hoàn toàn.
* **Các hàm này được thiết kế cho xử lý cả video offline, KHÔNG có cơ chế cập nhật frame-by-frame.**

**Hệ quả cho interface `RPPGMethod` (K1.3) với `update(frame)`:**
* **Không thể gọi thẳng** `POS_WANG(frame, fs)` với 1 frame duy nhất trong vòng lặp realtime — kết quả sẽ vô nghĩa (cửa sổ quá ngắn, không có context thời gian).
* **Bắt buộc phải có lớp wrapper sliding window buffer** bọc quanh các hàm REUSE này:

```python
class POSWrapper:
    def __init__(self, fs, window_sec=10.0):
        self.fs = fs
        self.window_size = int(window_sec * fs)
        self.buffer = []          # sliding window buffer

    def update(self, frame):      # gọi mỗi frame
        self.buffer.append(frame)
        if len(self.buffer) > self.window_size:
            self.buffer.pop(0)
        if len(self.buffer) < self.window_size:
            return None           # chưa đủ dữ liệu

        frames_array = np.array(self.buffer)  # (T, H, W, 3)
        bvp = POS_WANG(frames_array, self.fs)
        return bvp[-1]            # chỉ lấy giá trị mới nhất
```

* Cần quyết định chiến lược refresh: **chạy lại toàn bộ window mỗi frame** (chính xác nhưng tốn CPU) hay **chỉ chạy lại mỗi N frame** (hiệu quả hơn, trễ thêm N/fs giây).

---

## 7. RỦI RO PHÁP LÝ & NÚT THẮT KỸ THUẬT

1. **Rủi ro Bản quyền (Responsible AI License — RAIL):**
   * Repo gốc được cấp phép theo RAIL License (nghiêm cấm sử dụng trực tiếp để chẩn đoán bệnh án hoặc thẩm định bảo hiểm thương mại).
   * **Giải pháp cho Team:** Không copy nguyên vẹn codebase của repo. Chỉ tự hiện thực lại công thức toán học mở (POS 2017, CHROM 2013) đã công bố trên các tạp chí khoa học IEEE để đảm bảo tính pháp lý sạch (Clean-room design).

2. **Rủi ro Bộ lọc 2 chiều trong Real-time (`filtfilt` non-causal):**
   * Hàm `scipy.signal.filtfilt` là bộ lọc phi nhân quả (yêu cầu dữ liệu đầy đủ 2 chiều thời gian để triệt tiêu lệch pha). Khi áp dụng cho luồng streaming, nếu gọi trên từng block rời rạc sẽ gây giật mép tín hiệu.
   * **Giải pháp:** Duy trì sliding window có độ gối đầu (overlap), ví dụ giữ buffer 10 giây và dịch chuyển 1 giây mỗi chu kỳ cập nhật HR.

3. **Rủi ro Rung lắc khung khuôn mặt (ROI Jittering):**
   * Thuật toán Haar Cascade mặc định trong repo rất nhạy cảm với góc quay đầu, gây rung giật khung hình và tạo nhiễu trực tiếp vào kênh RGB.
   * **Giải pháp:** Thay thế bằng **MediaPipe Face Mesh** để trích xuất trực tiếp tọa độ các mốc da ổn định (Trán và 2 bên Má).

4. **Rủi ro kỹ thuật: Nhầm thứ tự kênh màu RGB vs BGR:**
   * OpenCV (`cv2`) trả về frame theo thứ tự **BGR mặc định**. Các thuật toán POS và CHROM giả định kênh 0 = R, kênh 1 = G, kênh 2 = B.
   * Nếu rgb_buffer của AIVitals Face/ROI module được tạo từ frame BGR mà **không convert** → công thức `Xs = 3R - 2G` sẽ thực ra tính `3B - 2G` → **kết quả HR sai hoàn toàn nhưng không có exception, không có warning, rất khó debug**.
   * **Giải pháp:** Bắt buộc `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` hoặc `frame[:,:,::-1]` trước khi tạo rgb_buffer. Thêm unit test kiểm tra thứ tự kênh (kênh R trên mặt người thường có giá trị cao hơn kênh B đáng kể).

5. **Rủi ro kiến trúc: Batch API không tương thích với Streaming update():**
   * Tất cả hàm unsupervised nhận cả video một lần (batch/offline). Không có state nội bộ.
   * Gọi thẳng trong vòng lặp frame-by-frame → vô nghĩa.
   * **Giải pháp:** Bắt buộc có sliding window wrapper (xem mục 6.5). Phải quyết định trade-off refresh rate vs CPU usage trước khi implement.

6. **Kiến trúc Tích hợp Hệ thống (Pipeline Streaming vs. Repo CLI):**
   * Repo gốc được viết dưới dạng CLI xử lý file video offline (`main.py --config_file ...`).
   * **Giải pháp:** Team cần bọc module Signal thành một Worker/Service độc lập (qua WebSocket hoặc Shared Memory) để nhận frame liên tục từ Camera và đẩy kết quả sang Backend/Frontend theo thời gian thực.

---

## 8. KHOẢNG TRỐNG CHỨC NĂNG SO VỚI YÊU CẦU PIPELINE (FUNCTIONAL GAPS)

Đối chiếu với mục tiêu toàn diện của pipeline AIVitals (**Camera → ROI → RGB → rPPG → BVP → Quality → HR/HRV/RR**), repo `rPPG-Toolbox` còn thiếu 3 thành phần cốt lõi:

### 8.1. Thiếu tính toán biến thiên nhịp tim HRV (Heart Rate Variability)
* **Hiện trạng repo:** Hoàn toàn **không có mã nguồn tính toán HRV**. Repo chỉ xuất ra sóng BVP và tính nhịp tim trung bình HR (bpm).
* **Giải pháp bổ sung:**
  * Dùng thuật toán phát hiện đỉnh tâm thu (Systolic Peak Detection) chính xác trên sóng BVP sau khi lọc sạch.
  * Tính chuỗi khoảng cách liên nhịp `IBI_i = t_i - t_(i-1)` (Inter-Beat Interval, ms).
  * Tính các chỉ số HRV cơ bản miền thời gian:
    * **SDNN** = sqrt(1/(N-1) * sum((IBI_i - mean_IBI)^2)) (Độ lệch chuẩn khoảng cách nhịp).
    * **RMSSD** = sqrt(1/(N-1) * sum((IBI_(i+1) - IBI_i)^2)) (Chỉ số phản ánh trương lực đối giao cảm).
  * Khuyến nghị tận dụng thư viện `neurokit2` (đã có trong `requirements.txt`) để trích xuất nhanh các chỉ số HRV tiêu chuẩn y tế.

### 8.2. Thiếu tính toán nhịp thở RR (Respiration Rate) cho nhóm Unsupervised
* **Hiện trạng repo:** Tính năng xuất nhịp thở RR chỉ hỗ trợ ở 2 mô hình Deep Learning đa nhiệm (`TS-CAN` và `BigSmall`). Các thuật toán Unsupervised (POS, CHROM, GREEN) **không trích xuất nhịp thở**.
* **Giải pháp bổ sung:**
  * Sóng nhịp thở điều hòa nhịp tim theo cơ chế hô hấp tự nhiên (Respiratory Sinus Arrhythmia — RSA) và tạo ra dao động chậm trên biên độ sóng BVP.
  * Trích xuất tín hiệu hô hấp từ BVP bằng bộ lọc dải thông tần số thở [0.1, 0.5] Hz (tương ứng 6–30 nhịp thở/phút).
  * Dùng biến đổi FFT trên tín hiệu hô hấp để tìm đỉnh tần số thở chính `RR_bpm = f_resp × 60`.

### 8.3. Thiếu xử lý biến thiên FPS thực tế của Webcam (Variable Frame Rate)
* **Hiện trạng repo:** Toàn bộ thuật toán giả định tần số lấy mẫu là cố định tuyệt đối (FS = 30.0 Hz).
* **Hiện trạng camera thực:** Webcam thực tế luôn bị trôi khung hình (27~31 FPS) tùy thuộc vào ánh sáng môi trường và tải CPU của máy. Nếu đưa dữ liệu này trực tiếp vào FFT với giả định 30 FPS, nhịp tim ước tính sẽ bị lệch từ 2–5 bpm.
* **Giải pháp bổ sung:**
  * Ghi nhận chính xác mốc thời gian thực `timestamp_i` của từng frame khi đọc từ camera.
  * Thực hiện **Nội suy tuyến tính (Linear Resampling)** mảng RGB buffer theo mốc thời gian chuẩn đều đặn (1/30.0s) trước khi đưa vào thuật toán POS/CHROM.

---

## 9. KẾ HOẠCH HÀNH ĐỘNG CHO TOÀN TEAM (ACTION PLAN)

Dựa trên kết quả audit, các đầu việc kỹ thuật cụ thể được phân bổ cho từng vị trí:

| Vị trí / Thành viên | Đầu việc kỹ thuật ưu tiên | Đầu ra mong đợi (Deliverables) |
| :--- | :--- | :--- |
| **Signal / Algorithm Dev** | 1. Tách hàm `POS` & `detrend` thành module nhận buffer (N, 3) — phải tách riêng bước spatial avg ra ngoài, không "chỉ bỏ 1 dòng đọc ảnh" (xem mục 4.A về process_video).<br>2. **[MỚI]** Viết `SlidingWindowWrapper` bọc tất cả hàm REUSE — cần trước khi tích hợp interface `update(frame)` (xem mục 6.5).<br>3. **[MỚI]** Viết hàm `calculate_snr_runtime(bvp, fs)` tự suy f0 từ phổ tín hiệu ước tính (không cần ground-truth). Tích hợp fallback periodicity + cross-ROI check (xem mục 6.3).<br>4. **[MỚI]** Thêm bước `cv2.COLOR_BGR2RGB` convert bắt buộc trước khi tạo rgb_buffer (xem mục 6.4 & mục 7 rủi ro 4).<br>5. Viết hàm nội suy Resampling FPS dựa trên timestamp thực.<br>6. Hiện thực thuật toán phát hiện đỉnh IBI → tính HRV (SDNN, RMSSD).<br>7. Viết hàm trích xuất nhịp thở RR bằng dải lọc [0.1, 0.5] Hz. | Module `src/signal/` độc lập, siêu nhẹ (chỉ phụ thuộc `numpy`, `scipy`). |
| **AI Model Dev** | 1. Nghiên cứu sâu kiến trúc `DeepPhys` và `EfficientPhys` (2 model nhẹ nhất có thể chạy realtime).<br>2. Chuẩn bị pipeline huấn luyện / fine-tuning trên dataset chuẩn (UBFC-rPPG / PURE).<br>3. Chuẩn bị định dạng export mô hình sang ONNX để tích hợp vào V2. | File model weights `.onnx` hoặc script inference PyTorch tối ưu. |
| **Backend Dev (Spring / API)** | 1. Xây dựng dịch vụ kết nối (WebSocket / REST Service) giao tiếp với luồng xử lý Signal qua JSON.<br>2. Thiết kế cơ sở dữ liệu lưu trữ lịch sử phiên đo (User, HR, HRV, RR, SQI, Timestamps).<br>3. Đảm bảo luồng chuyển tiếp dữ liệu thời gian thực ra Frontend không bị nghẽn. | WebSocket Endpoint `/ws/vitals` & CSDL lưu trữ lịch sử sinh hiệu. |
| **Frontend Dev** | 1. Thu luồng Webcam và vẽ khung hướng dẫn khuôn mặt (Face ROI Guide).<br>2. Nhận dữ liệu từ WebSocket để vẽ đồ thị sóng BVP thời gian thực (rolling waveform).<br>3. Hiển thị bảng chỉ số: Nhịp tim (HR), Nhịp thở (RR), Trạng thái căng thẳng (HRV), Thanh chất lượng tín hiệu (SQI). | Giao diện Dashboard đo sinh hiệu trực quan, mượt mà. |
