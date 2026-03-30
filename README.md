# 串口电压可视化控制（Python）

这个工具用 `tkinter + pyserial + matplotlib` 做了一个桌面界面，替代 PuTTY 发送命令，并增加了实时曲线显示。

## 功能
- 串口参数可配置（默认：COM3, 115200, 8N1, 无流控）
- 一键发送设备命令：`id?`、`enable=1/0`、`value?`、`enable?`
- 输入“目标输出电压(V)”，自动根据线性模型反算 `value=0..65535`
- 实时曲线：目标输出电压、拟合输出电压、串口返回 monitor 值
- 日志窗口显示收发数据

## 线性模型
根据你的拟合结果：

- `monitor = intercept + slope * value`
- 默认：`slope = -0.000303`，`intercept = 9.958395`
- monitor 与实际输出约 `20:1`

程序内部换算：

1. `monitor_target = Vout_target * ratio`
2. `value = (monitor_target - intercept) / slope`
3. 四舍五入并限制到 `[0, 65535]`

> 注意：`value=0` 为最大输出，`value=65535` 为最小输出（反向关系）。

## 安装依赖
```bash
pip install -r requirements.txt
```

## 运行
```bash
python serial_voltage_gui.py
```

## 使用步骤
1. 连接设备并确认串口（Windows 常见 COM3）。
2. 点击“连接”。
3. 点击“输出使能 ON”（`enable=1`）。
4. 输入目标输出电压后点击“写入 value”。
5. 观察右侧实时曲线（可点击“清空曲线”重置）。
6. 如需精调，请修改 slope / intercept / ratio（根据实测重新标定）。

## 下位机回读 monitor 的兼容格式
程序会尝试从串口返回中解析 monitor，支持：
- `monitor=9.12`
- `monitor: 9.12`
- `9.12`（纯数字）

## 封装 EXE（Windows）
在 Windows 的命令行（建议 Python 3.10+）执行：

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name SerialVoltageGUI serial_voltage_gui.py
```

生成文件：
- `dist/SerialVoltageGUI.exe`

如果你希望 exe 启动更快，也可以不用 `--onefile`：
```bash
pyinstaller --noconfirm --windowed --name SerialVoltageGUI serial_voltage_gui.py
```

## 标定建议
你可实测多个点后重新线性拟合得到更准确参数，再填回界面：
- 自变量：`value`
- 因变量：`monitor(V)`
- 拟合得到 `slope` 和 `intercept`


## 一键打包（build_exe.bat）
如果你已经把 `serial_voltage_gui.py` 下载到本地：

1. 把 `build_exe.bat` 也放到**同一个文件夹**。
2. 双击运行 `build_exe.bat`（建议右键“以管理员身份运行”）。
3. 脚本会自动：
   - 检测 Python
   - 安装 `pyinstaller`
   - 安装依赖（优先 `requirements.txt`）
   - 生成 `dist/SerialVoltageGUI.exe`
4. 打包完成后，直接运行 `dist/SerialVoltageGUI.exe`。

> 若双击窗口一闪而过，请在 CMD 中手动执行 `build_exe.bat` 查看报错信息。


### 如果双击 bat 报乱码/“不是内部或外部命令”
这通常是 bat 文件编码或复制方式导致的（例如从网页复制粘贴后混入不可见字符）。

请按下面方式处理：
1. 不要手动复制 bat 内容，直接在 GitHub 点 `build_exe.bat` -> `Raw` -> 另存为。
2. 文件名必须是 `build_exe.bat`，不是 `build_exe.bat.txt`。
3. 用记事本打开后另存为 **ANSI** 或 **UTF-8（带 BOM）** 再试。
4. 在 `cmd` 中进入该目录后执行：
   ```bat
   build_exe.bat
   ```

## 串口连接报错：`WinError 121 / 信号灯超时时间已到`
如果弹窗出现类似：

`could not open port 'COM3': OSError(22, '信号灯超时时间已到', None, 121)`

可按以下顺序排查：
1. 关闭其他占用串口的软件（PuTTY、串口助手、Arduino 串口监视器等）。
2. 拔插 USB 转串口线，等待 3 秒，再点“刷新端口”。
3. 在设备管理器确认端口号是否变化（COM3 可能变成 COM4/COM5）。
4. 更换 USB 口（尽量直连主板）或更换数据线。
5. 避免通过无源 HUB，可能供电不足导致超时。
6. 以管理员身份运行 EXE 后重试。

## 收到 `CMD_NOT_DEFINED`（命令格式可能不匹配）
如果日志里出现类似：`enable=1Command error CMD_NOT_DEFINED`，通常是命令结束符不匹配。

本工具当前固定使用 `CR`（`\\r`）作为命令结束符（与你下位机一致）。  
若后续更换设备需要 `LF` 或 `CRLF`，可再按新协议调整。
