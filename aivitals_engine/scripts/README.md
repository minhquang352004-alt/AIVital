# Signal Pipeline Runner (`run_signal_pipeline.py`)

Script mô phỏng luồng camera thời gian thực trên video để kiểm thử Signal Pipeline của Khang: **Frame → Face/ROI → Buffer → rPPG → BVP + SQI**.

---

## 1. Dữ Liệu Kiểm Thử (Video Dataset)

File video raw (`vid.avi` ~2.2 GB) không đưa lên Git do dung lượng lớn. 

* 🔗 **Google Drive:** `https://drive.google.com/file/d/1MJjRH8jvtgqR7DdRpZ0nyrY3fkeCB5A8/view?usp=sharing`
* 📁 **Vị trí lưu:** Tải về và đặt tại `aivitals_engine/samples/vid.avi` (hoặc chỉ định qua `--video <path>`).

---

## 2. Cách Chạy (Từ thư mục gốc `AIVital/`)

### 🔹 So sánh cùng lúc cả 3 phương pháp (GREEN, CHROM, POS)
```powershell
# Chạy toàn bộ video
python aivitals_engine/scripts/run_signal_pipeline.py --all-methods

# Hoặc test nhanh 30 giây đầu
python aivitals_engine/scripts/run_signal_pipeline.py --all-methods --max-sec 30
```

### 🔹 Chạy từng phương pháp cụ thể
```powershell
# Mặc định là POS
python aivitals_engine/scripts/run_signal_pipeline.py --method POS

# Chạy với CHROM
python aivitals_engine/scripts/run_signal_pipeline.py --method CHROM

# Chạy với GREEN
python aivitals_engine/scripts/run_signal_pipeline.py --method GREEN
```

---

## 3. Kết Quả Đầu Ra
* Sóng BVP xuất ra file CSV tại: `aivitals_engine/outputs/validate_<method>_bvp.csv`.
* Báo cáo in trực tiếp trên terminal: Face OK %, Artifact count, SQI trung bình, và nhịp tim ước lượng (FFT / Peak).
