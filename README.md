# Tool Rejoin Roblox Mobile (Fix Python 3.13)

Tool Rejoin tự động cho Roblox Mobile / Termux Android. Đã được sửa lỗi xung đột phiên bản **Python 3.14** của Termux bằng cách cài và ghim môi trường về đúng **Python 3.13.15** mà tool yêu cầu.

## 📦 Mục 1: Lệnh Cài Đặt (Đã bao gồm tải tool tự động & fix Python 3.13)

Mở **Termux** và dán lệnh:

```bash
. <(curl -sL https://raw.githubusercontent.com/shinn1603/Tool_rejoin_rb/main/Setubtoolrejoin)
```
*(Script sẽ tự động cài Python 3.13, thư viện và tải sẵn `obf-oldzmtool.py` vào `/sdcard/Download`)*.

---

## ⚙️ Mục 2: Lệnh Chạy Tool

### Cách 1: Lệnh Chạy Tool Cũ (obf-oldzmtool.py)
```bash
su -c "export PATH=$PATH:/data/data/com.termux/files/usr/bin && export TERM=xterm-256color && cd /sdcard/Download && python obf-oldzmtool.py"
```
*(Hoặc gõ phím tắt ngắn gọn: `rejoin-old`)*

### Setup Package trong Menu:
- Chọn **Số 6** → nhập `zam` nếu dùng Clone Free
- Chọn **Số 6** → nhập `vip` nếu dùng Clone VIP

---

### Cách 2: Chạy Bản Mới / Bản VIP
- **Bản mới:** `rejoin` (hoặc `python /sdcard/Download/zamtoolrejoinnewtool.py`)
- **Bản VIP:** `python /sdcard/Download/viprejoin.py`
