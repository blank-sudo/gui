import re
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except ImportError:
    FigureCanvasTkAgg = None
    Figure = None


class SerialVoltageApp:
    """串口电压控制界面：输入目标输出电压，自动换算为 value=0..65535 并下发。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("COM 串口电压控制")
        self.root.geometry("1060x760")

        self.ser = None
        self.read_thread = None
        self.stop_read = threading.Event()

        # 串口参数（默认与你的设备一致）
        self.port_var = tk.StringVar(value="COM3")
        self.baud_var = tk.IntVar(value=115200)
        self.databits_var = tk.IntVar(value=8)
        self.stopbits_var = tk.StringVar(value="1")
        self.parity_var = tk.StringVar(value="None")
        self.flow_var = tk.StringVar(value="None")
        self.eol_var = tk.StringVar(value="CRLF")

        # 标定参数：monitor = intercept + slope * value
        self.slope_var = tk.DoubleVar(value=-0.000303)
        self.intercept_var = tk.DoubleVar(value=9.958395)
        self.monitor_ratio_var = tk.DoubleVar(value=20.0)  # monitor:output = 20:1

        # 控制参数
        self.target_out_voltage_var = tk.DoubleVar(value=0.0)
        self.last_value_var = tk.IntVar(value=0)
        self.last_monitor_var = tk.DoubleVar(value=0.0)

        # 实时曲线缓存（最近 500 点）
        self.max_points = 500
        self.t_data = deque(maxlen=self.max_points)
        self.target_vout_data = deque(maxlen=self.max_points)
        self.fit_vout_data = deque(maxlen=self.max_points)
        self.monitor_data = deque(maxlen=self.max_points)
        self.chart_enabled = Figure is not None and FigureCanvasTkAgg is not None

        self._build_ui()
        self.refresh_ports()

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 6}

        serial_frame = ttk.LabelFrame(self.root, text="串口连接")
        serial_frame.pack(fill="x", padx=12, pady=8)

        ttk.Label(serial_frame, text="端口").grid(row=0, column=0, **pad)
        self.port_cb = ttk.Combobox(serial_frame, textvariable=self.port_var, width=14)
        self.port_cb.grid(row=0, column=1, **pad)

        ttk.Button(serial_frame, text="刷新端口", command=self.refresh_ports).grid(row=0, column=2, **pad)
        ttk.Label(serial_frame, text="波特率").grid(row=0, column=3, **pad)
        ttk.Entry(serial_frame, textvariable=self.baud_var, width=10).grid(row=0, column=4, **pad)

        ttk.Label(serial_frame, text="Data bits").grid(row=1, column=0, **pad)
        ttk.Combobox(serial_frame, textvariable=self.databits_var, values=[5, 6, 7, 8], width=12).grid(row=1, column=1, **pad)

        ttk.Label(serial_frame, text="Stop bits").grid(row=1, column=2, **pad)
        ttk.Combobox(serial_frame, textvariable=self.stopbits_var, values=["1", "1.5", "2"], width=10).grid(row=1, column=3, **pad)

        ttk.Label(serial_frame, text="Parity").grid(row=1, column=4, **pad)
        ttk.Combobox(serial_frame, textvariable=self.parity_var, values=["None", "Even", "Odd", "Mark", "Space"], width=12).grid(row=1, column=5, **pad)

        ttk.Label(serial_frame, text="Flow").grid(row=1, column=6, **pad)
        ttk.Combobox(serial_frame, textvariable=self.flow_var, values=["None", "RTS/CTS", "XON/XOFF"], width=10).grid(row=1, column=7, **pad)
        ttk.Label(serial_frame, text="结束符").grid(row=0, column=8, **pad)
        ttk.Combobox(
            serial_frame,
            textvariable=self.eol_var,
            values=["CR", "LF", "CRLF", "None"],
            width=8,
            state="readonly",
        ).grid(row=0, column=9, **pad)

        ttk.Button(serial_frame, text="连接", command=self.connect_serial).grid(row=0, column=6, **pad)
        ttk.Button(serial_frame, text="断开", command=self.disconnect_serial).grid(row=0, column=7, **pad)

        calib_frame = ttk.LabelFrame(self.root, text="线性模型标定")
        calib_frame.pack(fill="x", padx=12, pady=8)

        ttk.Label(calib_frame, text="Slope").grid(row=0, column=0, **pad)
        ttk.Entry(calib_frame, textvariable=self.slope_var, width=14).grid(row=0, column=1, **pad)

        ttk.Label(calib_frame, text="Intercept").grid(row=0, column=2, **pad)
        ttk.Entry(calib_frame, textvariable=self.intercept_var, width=14).grid(row=0, column=3, **pad)

        ttk.Label(calib_frame, text="monitor:output 比例").grid(row=0, column=4, **pad)
        ttk.Entry(calib_frame, textvariable=self.monitor_ratio_var, width=10).grid(row=0, column=5, **pad)

        control_frame = ttk.LabelFrame(self.root, text="电压控制")
        control_frame.pack(fill="x", padx=12, pady=8)

        ttk.Label(control_frame, text="目标输出电压(V)").grid(row=0, column=0, **pad)
        ttk.Entry(control_frame, textvariable=self.target_out_voltage_var, width=16).grid(row=0, column=1, **pad)

        ttk.Button(control_frame, text="计算 value", command=self.calculate_only).grid(row=0, column=2, **pad)
        ttk.Button(control_frame, text="写入 value", command=self.write_target_voltage).grid(row=0, column=3, **pad)

        ttk.Button(control_frame, text="输出使能 ON", command=lambda: self.send_command("enable=1")).grid(row=1, column=0, **pad)
        ttk.Button(control_frame, text="输出使能 OFF", command=lambda: self.send_command("enable=0")).grid(row=1, column=1, **pad)

        ttk.Button(control_frame, text="读取 ID", command=lambda: self.send_command("id?", expect_reply=True)).grid(row=1, column=2, **pad)
        ttk.Button(control_frame, text="读取 value", command=lambda: self.send_command("value?", expect_reply=True)).grid(row=1, column=3, **pad)
        ttk.Button(control_frame, text="读取 enable", command=lambda: self.send_command("enable?", expect_reply=True)).grid(row=1, column=4, **pad)

        ttk.Button(control_frame, text="清空曲线", command=self.clear_plot_data).grid(row=1, column=5, **pad)

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", padx=12, pady=6)

        ttk.Label(status_frame, text="计算 value").grid(row=0, column=0, **pad)
        ttk.Label(status_frame, textvariable=self.last_value_var).grid(row=0, column=1, **pad)

        ttk.Label(status_frame, text="对应 monitor(V)").grid(row=0, column=2, **pad)
        ttk.Label(status_frame, textvariable=self.last_monitor_var).grid(row=0, column=3, **pad)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=12, pady=8)

        log_frame = ttk.LabelFrame(body, text="串口日志")
        log_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.log_text = tk.Text(log_frame, wrap="word", height=22)
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

        plot_frame = ttk.LabelFrame(body, text="实时曲线")
        plot_frame.pack(side="right", fill="both", expand=True, padx=(6, 0))

        if self.chart_enabled:
            self.figure = Figure(figsize=(6.2, 4.4), dpi=100)
            self.ax = self.figure.add_subplot(111)
            self.line_target, = self.ax.plot([], [], label="目标输出电压 Vout_target (V)", linewidth=1.8)
            self.line_fit, = self.ax.plot([], [], label="拟合输出电压 Vout_fit (V)", linewidth=1.6)
            self.line_monitor, = self.ax.plot([], [], label="监测电压 monitor (V)", linewidth=1.2)
            self.ax.set_xlabel("时间(s)")
            self.ax.set_ylabel("电压(V)")
            self.ax.grid(True, alpha=0.25)
            self.ax.legend(loc="best")

            self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
            self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)
            self.root.after(400, self._refresh_plot)
        else:
            ttk.Label(
                plot_frame,
                text="未安装 matplotlib，无法显示实时曲线。\n请执行: pip install matplotlib",
                foreground="red",
                justify="center",
            ).pack(fill="both", expand=True, padx=8, pady=8)

        self.log("程序启动。请先连接串口。")

    def refresh_ports(self) -> None:
        if list_ports is None:
            return
        ports = [p.device for p in list_ports.comports()]
        self.port_cb["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])

    def _serial_params(self):
        parity_map = {
            "None": serial.PARITY_NONE,
            "Even": serial.PARITY_EVEN,
            "Odd": serial.PARITY_ODD,
            "Mark": serial.PARITY_MARK,
            "Space": serial.PARITY_SPACE,
        }
        stop_map = {
            "1": serial.STOPBITS_ONE,
            "1.5": serial.STOPBITS_ONE_POINT_FIVE,
            "2": serial.STOPBITS_TWO,
        }

        xonxoff = self.flow_var.get() == "XON/XOFF"
        rtscts = self.flow_var.get() == "RTS/CTS"

        return {
            "port": self.port_var.get(),
            "baudrate": self.baud_var.get(),
            "bytesize": self.databits_var.get(),
            "parity": parity_map[self.parity_var.get()],
            "stopbits": stop_map[self.stopbits_var.get()],
            "xonxoff": xonxoff,
            "rtscts": rtscts,
            "timeout": 0.2,
        }

    def connect_serial(self) -> None:
        if serial is None:
            messagebox.showerror("缺少依赖", "请先安装 pyserial: pip install pyserial")
            return
        if self.ser and self.ser.is_open:
            self.log("串口已连接。")
            return
        try:
            self.ser = serial.Serial(**self._serial_params())
            self.log(f"已连接: {self.ser.port}, {self.ser.baudrate} bps")
            self.stop_read.clear()
            self.read_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.read_thread.start()
            return
        except Exception as first_error:
            # Windows 某些 USB 串口会偶发 WinError 121，短暂重试一次
            self.log(f"首次连接失败，准备重试: {first_error}")
            time.sleep(0.3)

        try:
            self.ser = serial.Serial(**self._serial_params())
            self.log(f"重试连接成功: {self.ser.port}, {self.ser.baudrate} bps")
            self.stop_read.clear()
            self.read_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.read_thread.start()
        except Exception as e:
            msg = self._format_connect_error(e)
            messagebox.showerror("连接失败", msg)
            self.log(f"连接失败: {msg}")

    def _format_connect_error(self, err: Exception) -> str:
        text = str(err)
        low = text.lower()
        port = self.port_var.get()

        if "121" in low or "信号灯超时时间已到" in text:
            return (
                f"{text}\n\n"
                f"排查建议（{port}）：\n"
                "1) 关闭 PuTTY/串口助手/Arduino Serial Monitor 等占用串口的软件。\n"
                "2) 拔插 USB 转串口线，等待 3 秒后点“刷新端口”再连接。\n"
                "3) 打开设备管理器确认端口号是否变化（可能从 COM3 变为 COM4/COM5）。\n"
                "4) 更换 USB 口（优先主板后置口）或更换数据线。\n"
                "5) 若是 USB 集线器供电不足，请改直连电脑。\n"
            )
        if "access is denied" in low or "权限" in text:
            return (
                f"{text}\n\n"
                "串口被占用或权限不足：\n"
                "1) 关闭其他串口程序。\n"
                "2) 以管理员身份运行本程序后重试。"
            )
        if "file not found" in low or "找不到" in text:
            return (
                f"{text}\n\n"
                f"未找到端口 {port}，请先点击“刷新端口”并重新选择正确 COM 号。"
            )
        return text

    def disconnect_serial(self) -> None:
        self.stop_read.set()
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
            self.log("串口已断开。")

    def _reader_loop(self) -> None:
        rx_buffer = ""
        while not self.stop_read.is_set() and self.ser and self.ser.is_open:
            try:
                chunk = self.ser.read(self.ser.in_waiting or 1)
                if not chunk:
                    continue
                rx_buffer += chunk.decode(errors="ignore")
                parts = re.split(r"[\r\n]+", rx_buffer)
                rx_buffer = parts[-1]
                for text in parts[:-1]:
                    text = text.strip()
                    if text:
                        self.root.after(0, self.log, f"<- {text}")
                        self.root.after(0, self._append_monitor_from_line, text)
            except Exception as e:
                self.root.after(0, self.log, f"读串口异常: {e}")
                break

    def _append_monitor_from_line(self, text: str) -> None:
        # 兼容如下形式： monitor=9.12 / monitor: 9.12 / 9.12
        match = re.search(r"monitor\s*[:=]\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if not match:
            plain = re.fullmatch(r"-?\d+(?:\.\d+)?", text)
            if plain:
                val = float(plain.group(0))
            else:
                return
        else:
            val = float(match.group(1))

        t = time.time()
        self.t_data.append(t)
        self.monitor_data.append(val)
        if len(self.target_vout_data) < len(self.t_data):
            self.target_vout_data.append(float("nan"))
        if len(self.fit_vout_data) < len(self.t_data):
            self.fit_vout_data.append(float("nan"))

    def log(self, msg: str) -> None:
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def send_command(self, cmd: str, expect_reply: bool = False) -> None:
        if not (self.ser and self.ser.is_open):
            messagebox.showwarning("未连接", "请先连接串口")
            return
        try:
            clean_cmd = cmd.strip().lower()
            eol_map = {
                "CR": "\r",
                "LF": "\n",
                "CRLF": "\r\n",
                "None": "",
            }
            eol = eol_map.get(self.eol_var.get(), "\r\n")
            wire = (clean_cmd + eol).encode("ascii")
            self.ser.write(wire)
            self.log(f"-> {clean_cmd} [EOL={self.eol_var.get()}]")
            if expect_reply:
                self.ser.flush()
        except Exception as e:
            self.log(f"发送失败: {e}")

    def voltage_to_value(self, v_out: float) -> tuple[int, float]:
        slope = self.slope_var.get()
        intercept = self.intercept_var.get()
        ratio = self.monitor_ratio_var.get()

        if abs(slope) < 1e-12:
            raise ValueError("Slope 不能为 0")
        if abs(ratio) < 1e-12:
            raise ValueError("monitor:output 比例不能为 0")

        v_monitor = v_out * ratio
        value_float = (v_monitor - intercept) / slope
        value = int(round(value_float))

        value = max(0, min(65535, value))
        v_monitor_fit = intercept + slope * value
        return value, v_monitor_fit

    def _append_prediction_point(self, vout_target: float, v_monitor_fit: float) -> None:
        t = time.time()
        ratio = self.monitor_ratio_var.get()
        vout_fit = v_monitor_fit / ratio if abs(ratio) > 1e-12 else float("nan")

        self.t_data.append(t)
        self.target_vout_data.append(vout_target)
        self.fit_vout_data.append(vout_fit)
        if len(self.monitor_data) < len(self.t_data):
            self.monitor_data.append(float("nan"))

    def clear_plot_data(self) -> None:
        self.t_data.clear()
        self.target_vout_data.clear()
        self.fit_vout_data.clear()
        self.monitor_data.clear()
        self.log("已清空实时曲线数据。")

    def _refresh_plot(self) -> None:
        if not self.chart_enabled:
            return

        if self.t_data:
            t0 = self.t_data[0]
            x = [t - t0 for t in self.t_data]
            self.line_target.set_data(x, list(self.target_vout_data))
            self.line_fit.set_data(x, list(self.fit_vout_data))
            self.line_monitor.set_data(x, list(self.monitor_data))
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()

        self.root.after(400, self._refresh_plot)

    def calculate_only(self) -> None:
        try:
            vout = self.target_out_voltage_var.get()
            value, v_monitor_fit = self.voltage_to_value(vout)
            self.last_value_var.set(value)
            self.last_monitor_var.set(round(v_monitor_fit, 6))
            self._append_prediction_point(vout, v_monitor_fit)
            self.log(
                f"计算完成: Vout={vout:.6f} V -> value={value}, monitor≈{v_monitor_fit:.6f} V"
            )
        except Exception as e:
            messagebox.showerror("计算失败", str(e))

    def write_target_voltage(self) -> None:
        try:
            vout = self.target_out_voltage_var.get()
            value, v_monitor_fit = self.voltage_to_value(vout)
            self.last_value_var.set(value)
            self.last_monitor_var.set(round(v_monitor_fit, 6))
            self.send_command(f"value={value}")
            self._append_prediction_point(vout, v_monitor_fit)
            self.log(
                f"已下发: value={value} (目标Vout={vout:.6f} V, 拟合monitor≈{v_monitor_fit:.6f} V)"
            )
        except Exception as e:
            messagebox.showerror("写入失败", str(e))


def main() -> None:
    root = tk.Tk()
    app = SerialVoltageApp(root)

    def on_close() -> None:
        app.disconnect_serial()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
