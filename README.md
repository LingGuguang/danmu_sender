# B站直播弹幕发送工具 (danmu_sender)

在已登录 B 站的前提下，查看当前账号「关注中」正在直播的主播列表，选择直播间并发送弹幕。

## 功能

- 获取关注中正在直播的主播列表（主播名、直播标题）
- 在终端选择直播间，输入弹幕内容（最多 30 字）并发送
- 支持切换直播间、退出到选择界面或退出程序

## 环境要求

- Python 3.8+
- 已登录 B 站的 Cookie（见下方「Cookie 配置」）

## 安装

```bash
git clone https://github.com/YOUR_USERNAME/danmu_sender.git
cd danmu_sender
pip install -r requirements.txt
```

## 使用

```bash
# 推荐：一键更新依赖并运行
./run.sh

# 或直接运行
python -m danmu_sender
# 或
python main.py
```

### 交互说明

- **选择直播间**：输入列表中的序号；输入 `close` 退出程序。
- **发送弹幕**：
  - 输入内容后回车：发送弹幕（超过 30 字会自动截断）。
  - 直接回车：仅重新输入，不发送。
  - 输入 `exit`：返回「选择直播间」界面，可换一个房间。
  - 输入 `close`：退出程序。

## Cookie 配置

程序需要 B 站登录态（Cookie）才能获取关注列表和发送弹幕。按以下顺序尝试获取：

1. **本机 Chrome/Chromium**：若程序与浏览器在同一台机器且 Chrome 未运行，可自动读取（Linux 下 Chrome 运行时无法读取，会提示）。
2. **请求 B 站主页**：模仿浏览器访问主页，仅能拿到匿名 Cookie，无法发弹幕，仅作兜底。
3. **配置文件**：从浏览器复制 Cookie 写入 `~/.config/danmu_sender/cookies.txt`。

### 手动配置 Cookie（推荐在远程服务器或无法读 Chrome 时）

1. 在**本机**浏览器打开 https://www.bilibili.com 并登录。
2. 按 F12 → **应用 / Application** → **Cookie** → 选择 `https://www.bilibili.com`。
3. 复制 **SESSDATA** 和 **bili_jct** 的值（或整条 Cookie 字符串）。
4. 在运行程序的机器上创建配置文件：
   ```bash
   mkdir -p ~/.config/danmu_sender
   # 编辑 cookies.txt，格式示例（一行，分号分隔）：
   # SESSDATA=你的SESSDATA值; bili_jct=你的bili_jct值
   nano ~/.config/danmu_sender/cookies.txt
   ```

若程序在**远程服务器**运行、在**本机**浏览器登录，登录态在本地，服务器拿不到，必须用本方法：在本机复制 Cookie 后写入服务器上的 `~/.config/danmu_sender/cookies.txt`。Cookie 约一个月过期，过期后重新复制即可。

## 日志

- 目录：`runtime/logs/`
- 主文件：`danmu_sender.log`
- 单文件满 **500MB** 自动切分，保留 5 个备份
- 记录：Cookie 加载、API 请求、选择房间、发送弹幕及错误，便于排查

## 项目结构

```
danmu_sender/
├── README.md
├── requirements.txt
├── run.sh                 # 一键运行（可选更新依赖）
├── main.py                # 入口
├── runtime/
│   └── logs/              # 日志目录
└── danmu_sender/
    ├── __init__.py
    ├── __main__.py
    ├── logging_config.py  # 日志配置（500MB 切分）
    ├── cookie_loader.py   # Cookie 加载（Chrome / 请求 B 站 / 文件）
    ├── bilibili_api.py    # B 站 API：关注直播列表、发送弹幕、真实房间号
    └── cli.py             # 终端交互
```

## 依赖

- `requests`：HTTP 请求
- `browser-cookie3`：从本机 Chrome/Chromium 读取 Cookie（可选）

## 说明与免责

- 弹幕长度限制 30 字符，遵循 B 站直播间规则。
- 请勿用于刷屏、违规内容或自动化滥用，使用需遵守 [B 站用户协议](https://www.bilibili.com/blackboard/rule.html)。
