# -*- coding: utf-8 -*-
"""
Roblox Mobile Auto-Rejoin Tool (Open-Source Clean Edition)
Tác giả: shinn1603 & Community
Mô tả: Tự động phát hiện dis game, crash, lỗi mạng trên Roblox Mobile (Android/Termux) 
       và tự động Rejoin lại phòng chơi.
"""

import os
import sys
import time
import json
import subprocess
import threading
from datetime import datetime
from typing import List, Dict, Optional

# Kiểm tra thư viện
try:
    import requests
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
except ImportError:
    print("[!] Thiếu thư viện rich hoặc requests. Vui lòng chạy: pip install rich requests")
    sys.exit(1)

console = Console()
CONFIG_FILE = "rejoin_config.json"

DEFAULT_CONFIG = {
    "place_id": "2753915549",          # Mặc định (Blox Fruits)
    "job_id": "",                       # Server Job ID (nếu có)
    "private_server_link": "",          # Link VIP server (nếu có)
    "package_prefix": "com.roblox",     # Tiền tố package Roblox / Clone
    "packages": ["com.roblox.client"],  # Danh sách package theo dõi
    "check_interval": 15,               # Chu kỳ kiểm tra (giây)
    "max_idle_time": 60,                # Thời gian tối đa không thấy phản hồi (giây)
    "use_executor_heartbeat": True,     # Theo dõi qua file heartbeat của Executor
    "heartbeat_dir": "/sdcard/RobloxRejoin", # Thư mục lưu heartbeat
    "webhook_url": "",                  # Discord Webhook URL
    "device_name": "Android-Termux"
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception as e:
            console.print(f"[red]Lỗi đọc cấu hình: {e}. Dùng cấu hình mặc định.[/red]")
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

def run_cmd(cmd: str) -> str:
    """Chạy lệnh shell Android và trả về output"""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return res.stdout.strip()
    except Exception:
        return ""

class DiscordNotifier:
    @staticmethod
    def send(webhook_url: str, title: str, description: str, color: int = 0x00ff00):
        if not webhook_url:
            return
        payload = {
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "Roblox Auto Rejoin Clean Edition"}
            }]
        }
        try:
            threading.Thread(
                target=lambda: requests.post(webhook_url, json=payload, timeout=5),
                daemon=True
            ).start()
        except Exception:
            pass

class RobloxManager:
    def __init__(self, config: dict):
        self.config = config

    def detect_packages(self) -> List[str]:
        """Tự động tìm kiếm các package Roblox hoặc Roblox clone đang cài trên máy"""
        prefix = self.config.get("package_prefix", "com.roblox")
        out = run_cmd(f"pm list packages {prefix}")
        packages = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkg = line.replace("package:", "").strip()
                if pkg and pkg not in packages:
                    packages.append(pkg)
        if not packages:
            # Fallback nếu không có quyền pm list
            packages = ["com.roblox.client"]
        return packages

    def is_running(self, package: str) -> bool:
        """Kiểm tra process Roblox có đang chạy không"""
        pid = run_cmd(f"pidof {package}")
        return bool(pid.strip())

    def stop_roblox(self, package: str):
        """Buộc dừng ứng dụng Roblox"""
        run_cmd(f"am force-stop {package}")

    def launch_roblox(self, package: str):
        """Khởi động Roblox và Rejoin vào phòng game"""
        place_id = self.config.get("place_id", "").strip()
        job_id = self.config.get("job_id", "").strip()
        vip_link = self.config.get("private_server_link", "").strip()

        if vip_link:
            # Rejoin qua Link Private Server
            cmd = f'am start -a android.intent.action.VIEW -d "{vip_link}" {package}'
        elif place_id and job_id:
            # Rejoin qua PlaceId + JobId
            uri = f"roblox://experiences/start?placeId={place_id}&gameInstanceId={job_id}"
            cmd = f'am start -a android.intent.action.VIEW -d "{uri}" {package}'
        elif place_id:
            # Rejoin qua PlaceId chuẩn
            uri = f"roblox://placeId={place_id}"
            cmd = f'am start -a android.intent.action.VIEW -d "{uri}" {package}'
        else:
            cmd = f"monkey -p {package} -c android.intent.category.LAUNCHER 1"

        run_cmd(cmd)

    def generate_heartbeat_lua(self) -> str:
        """Tạo script Lua chép vào executor để báo hiệu tab đang sống"""
        hb_dir = self.config.get("heartbeat_dir", "/sdcard/RobloxRejoin")
        lua_code = f"""-- Auto Rejoin Heartbeat Script
task.spawn(function()
    local hbPath = "{hb_dir}/" .. tostring(game.Players.LocalPlayer.UserId) .. ".hb"
    while true do
        pcall(function()
            if writefile then
                writefile(hbPath, tostring(os.time()))
            end
        end)
        task.wait(5)
    end
end)
"""
        return lua_code

class RejoinEngine:
    def __init__(self, config: dict):
        self.config = config
        self.mgr = RobloxManager(config)
        self.running = False
        self.rejoin_counts: Dict[str, int] = {}
        self.last_alive: Dict[str, float] = {}

    def start(self):
        self.running = True
        packages = self.config.get("packages", [])
        interval = self.config.get("check_interval", 15)
        max_idle = self.config.get("max_idle_time", 60)
        webhook = self.config.get("webhook_url", "")
        hb_dir = self.config.get("heartbeat_dir", "/sdcard/RobloxRejoin")

        # Đảm bảo thư mục heartbeat tồn tại
        os.makedirs(hb_dir, exist_ok=True)

        console.print(Panel(
            f"[bold green]Auto Rejoin Engine đang chạy...[/bold green]\n"
            f"[cyan]Số lượng Package theo dõi:[/cyan] {len(packages)}\n"
            f"[cyan]Place ID:[/cyan] {self.config.get('place_id')}\n"
            f"[cyan]Chu kỳ kiểm tra:[/cyan] {interval}s\n"
            f"[yellow]Nhấn Ctrl + C để dừng.[/yellow]",
            title="ĐANG THEO DÕI REJOIN"
        ))

        for pkg in packages:
            self.rejoin_counts[pkg] = 0
            self.last_alive[pkg] = time.time()

        try:
            while self.running:
                now = time.time()
                for pkg in packages:
                    needs_rejoin = False
                    reason = ""

                    # Cách 1: Kiểm tra Process còn sống không
                    is_alive = self.mgr.is_running(pkg)

                    if not is_alive:
                        needs_rejoin = True
                        reason = "Ứng dụng bị văng / Crash (Process không tồn tại)"
                    else:
                        # Cách 2: Nếu bật kiểm tra Heartbeat qua Executor
                        if self.config.get("use_executor_heartbeat", True):
                            # Tìm file .hb mới nhất trong hb_dir
                            found_hb = False
                            for fname in os.listdir(hb_dir) if os.path.exists(hb_dir) else []:
                                if fname.endswith(".hb"):
                                    fpath = os.path.join(hb_dir, fname)
                                    try:
                                        mtime = os.path.getmtime(fpath)
                                        if (now - mtime) < max_idle:
                                            found_hb = True
                                            self.last_alive[pkg] = mtime
                                            break
                                    except Exception:
                                        pass
                            
                            if not found_hb and (now - self.last_alive.get(pkg, now)) > max_idle:
                                needs_rejoin = True
                                reason = f"Mất kết nối game / Màn hình Disconnect (Quá {max_idle}s không có phản hồi)"

                    if needs_rejoin:
                        self.rejoin_counts[pkg] = self.rejoin_counts.get(pkg, 0) + 1
                        rejoin_num = self.rejoin_counts[pkg]
                        console.print(f"[bold red][{datetime.now().strftime('%H:%M:%S')}][/bold red] [yellow]{pkg}[/yellow]: {reason}")
                        console.print(f"[bold cyan]=> Đang khởi động lại {pkg} (Lần rejoin: #{rejoin_num})...[/bold cyan]")

                        # Dừng app cũ, đợi 3s rồi bật lại
                        self.mgr.stop_roblox(pkg)
                        time.sleep(3)
                        self.mgr.launch_roblox(pkg)

                        # Reset mốc thời gian
                        self.last_alive[pkg] = time.time()

                        # Gửi Discord Webhook
                        if webhook:
                            DiscordNotifier.send(
                                webhook,
                                title=f"🔄 Tự Động Rejoin: {pkg}",
                                description=f"**Lý do:** {reason}\n**Place ID:** `{self.config.get('place_id')}`\n**Tổng số lần Rejoin:** #{rejoin_num}",
                                color=0xffa500
                            )

                    else:
                        console.print(f"[dim][{datetime.now().strftime('%H:%M:%S')}] {pkg}: Hoạt động bình thường[/dim]")

                time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]Đã tạm dừng Rejoin Engine.[/yellow]")
            self.running = False

def show_menu():
    cfg = load_config()
    mgr = RobloxManager(cfg)

    while True:
        console.clear()
        console.print(Panel(
            "[bold green]ROBLOX AUTO REJOIN - CLEAN OPEN-SOURCE EDITION[/bold green]\n"
            "[cyan]Mã nguồn mở, an toàn 100%, không virus, không obfuscate.[/cyan]",
            subtitle="Phiên bản 1.0.0"
        ))

        table = Table(title="Cấu hình hiện tại")
        table.add_column("Mục", style="bold cyan")
        table.add_column("Giá trị", style="white")

        table.add_row("Place ID (Game)", str(cfg.get("place_id", "Chưa đặt")))
        table.add_row("Server Job ID", str(cfg.get("job_id") or "Không dùng"))
        table.add_row("VIP Server Link", str(cfg.get("private_server_link") or "Không dùng"))
        table.add_row("Danh sách Packages", ", ".join(cfg.get("packages", [])) or "Chưa có")
        table.add_row("Chu kỳ kiểm tra", f"{cfg.get('check_interval', 15)} giây")
        table.add_row("Discord Webhook", "Đã bật" if cfg.get("webhook_url") else "Tắt")
        console.print(table)

        console.print("""
[bold yellow]MENU LỰA CHỌN:[/bold yellow]
 [1] Khởi chạy Auto Rejoin
 [2] Đổi Place ID (Game ID) hoặc Link VIP Server
 [3] Tự động quét và chọn các Package Roblox / Clone
 [4] Cấu hình Discord Webhook
 [5] Xuất mã Lua Heartbeat cho Executor (Delta/Fluxus/Codex)
 [6] Thử nghiệm Rejoin ngay 1 tab (Test Launch)
 [0] Thoát
        """)

        choice = Prompt.ask("Nhập lựa chọn của bạn", choices=["0", "1", "2", "3", "4", "5", "6"], default="1")

        if choice == "1":
            engine = RejoinEngine(cfg)
            engine.start()
            Prompt.ask("\nNhấn Enter để quay lại menu...")

        elif choice == "2":
            mode = Prompt.ask("Chọn kiểu Rejoin: [1] Place ID thường, [2] Link VIP Server", choices=["1", "2"], default="1")
            if mode == "1":
                new_id = Prompt.ask("Nhập Game Place ID mới (ví dụ: 2753915549)", default=str(cfg.get("place_id")))
                cfg["place_id"] = new_id
                cfg["private_server_link"] = ""
            else:
                new_link = Prompt.ask("Dán đường link VIP Server")
                cfg["private_server_link"] = new_link
            save_config(cfg)
            console.print("[green]Đã lưu cấu hình Game thành công![/green]")
            time.sleep(1.5)

        elif choice == "3":
            console.print("[yellow]Đang quét các package Roblox trên thiết bị...[/yellow]")
            pkgs = mgr.detect_packages()
            console.print(f"[green]Tìm thấy {len(pkgs)} package:[/green] {pkgs}")
            if Confirm.ask("Sử dụng danh sách package này để Auto Rejoin?", default=True):
                cfg["packages"] = pkgs
                save_config(cfg)
                console.print("[green]Đã cập nhật danh sách Package![/green]")
            time.sleep(2)

        elif choice == "4":
            wh = Prompt.ask("Nhập Discord Webhook URL (Bỏ trống để tắt)", default=cfg.get("webhook_url", ""))
            cfg["webhook_url"] = wh.strip()
            save_config(cfg)
            if wh:
                console.print("[green]Đang gửi tin nhắn thử nghiệm tới Discord...[/green]")
                DiscordNotifier.send(wh, "🔔 Roblox Rejoin Test", "Webhook đã được kết nối thành công từ Termux!")
            time.sleep(1.5)

        elif choice == "5":
            lua = mgr.generate_heartbeat_lua()
            hb_path = os.path.join(cfg.get("heartbeat_dir", "/sdcard/RobloxRejoin"), "autoexec_heartbeat.lua")
            try:
                os.makedirs(os.path.dirname(hb_path), exist_ok=True)
                with open(hb_path, "w", encoding="utf-8") as f:
                    f.write(lua)
                console.print(f"[green]Đã lưu script Lua vào: {hb_path}[/green]")
            except Exception:
                pass
            console.print(Panel(lua, title="MÃ LUA HEARTBEAT (BỎ VÀO THƯ MỤC AUTOEXEC CỦA EXECUTOR)"))
            Prompt.ask("\nNhấn Enter để tiếp tục...")

        elif choice == "6":
            pkgs = cfg.get("packages", ["com.roblox.client"])
            if pkgs:
                console.print(f"[cyan]Đang chạy thử khởi động: {pkgs[0]}...[/cyan]")
                mgr.launch_roblox(pkgs[0])
            time.sleep(2)

        elif choice == "0":
            console.print("[green]Tạm biệt![/green]")
            break

if __name__ == "__main__":
    show_menu()

