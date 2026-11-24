# CLAUDE.md - Yelena 的衣柜

## 项目概述

Windows 本地衣柜与搭配桌面软件（界面显示名 **Yelena 的衣柜**）。
用户导入自己衣服的
「正面 / 侧面 / 背面」三张透明背景 PNG，在画布上自由拼贴搭配，
再把整套搭配套到自己的全身照上预览。

技术栈：Python 3.11 + pywebview + 标准库 HTTP 服务 + SQLite + Pillow + 原生前端。

## 项目路径

`C:\Users\杨婷\Desktop\yangjun-closes`（Yelena 的衣柜，按实际路径修改）

## 文档体系（docs/）

| 文件 | 内容 |
|------|------|
| [docs/01-需求文档.md](docs/01-需求文档.md) | 需求、核心概念、功能清单（P0/P1/P2）、界面原则 |
| [docs/02-技术方案.md](docs/02-技术方案.md) | 架构、目录结构、建表 SQL、图片管线、旋转与画布算法 |
| [docs/03-开发规范.md](docs/03-开发规范.md) | 代码风格、命名、错误处理、文件模板 |
| [docs/04-执行步骤.md](docs/04-执行步骤.md) | 阶段划分、每阶段任务与验收标准 |
| [docs/05-版本管理.md](docs/05-版本管理.md) | Git 工作流、提交规范、分支与标签 |
| [docs/06-当前进度.md](docs/06-当前进度.md) | 朋友版当前状态、运行方式与待改项 |
| [docs/07-模特与搭配展示规划.md](docs/07-模特与搭配展示规划.md) | 基准模特展示、图片处理与未来搭配切换方案 |

## 工作流程

### 开发步骤
1. **一次只做一个功能点**，做完验证再继续下一个
2. 按需要记录自己的开发进度（本仓库不附带个人开发日志）
3. 遵循 `docs/04-执行步骤.md` 中的阶段划分
4. **每个功能点完成后必须提交并推送到远程仓库**：
   `git add <相关文件>` → `git commit` → `git push`
   远程地址与提交规范见 `docs/05-版本管理.md`

### 代码规范
- 遵循 PEP 8，行宽 100
- 中文注释 + 中文 docstring
- 每个文件开头有模块说明注释
- 数据库操作必须 try/except 包裹，异常转成 `ServiceError` 中文提示

## 关键约定（不要违反）

1. **Python 固定用 3.11**（`py -3.11`）。机器默认的 `python` 是 3.8，太旧。
2. 前端**不用框架、不用构建工具**，经典 `<script>` + `window.App` 命名空间。
3. 所有颜色/圆角/间距写在 `web/css/variables.css`，换皮肤只改变量。
4. 画布坐标一律**归一化到 0~1**，不存像素。
5. 图片展示用 WebP，原始 PNG 保留在 `data/garments/<id>/original/`。
6. 程序不调用任何 AI 服务，不内置抠图——图片由用户自己处理好再导入。
7. 数据目录：开发时在项目根 `data/`，打包后在 exe 同级 `data/`。
8. 删除衣服走二次确认；删除时先删数据库记录再删图片目录。
9. 图片视觉风格固定为 **3D 皮克斯动画风**（衣物三视角 + 动漫模特形象），
   由用户在外部 AI 工具生成后导入；程序不做风格转换，也不判断画风。
10. 衣物图片统一由用户自备，程序不接入任何图像生成 API。
11. 配饰在首页独立收纳区展示，摆放方式由 `display_style` 控制：
    `hang` 挂杆 / `bag` 纸袋 / `flat` 平放 / `drawer` 抽屉；配饰不套白色卡片。
12. 首页最下方是嵌入式衣帽柜：鞋、包、帽子和小件配饰按 `cabinet_slot`
    进入各自分区，每格独立木隔板，手动拖动换格，空格保留。
13. 左侧栏是衣橱目录（带件数），顶部只留搜索 / 筛选弹层 / 添加；
    分类导航不再放回顶部。
14. 界面为蓝水彩夜空风：雾蓝背景、奶油悬浮面板、金色挂杆、奶白衣帽柜、
    幼圆标题；搭配画布和上身图展示台必须保持纯白。
15. 启动等待封面约 4 秒淡出，点击立即跳过；设置页开关同时写
    cookie 和 `localStorage['yelena-welcome']`，cookie 不区分端口，
    随机端口启动也能记住“关闭”。
16. 搭配页顶部是「我的试衣模特」：五角度透明图存在 `data/model/`，
    可拖动旋转；模特图属于个人素材，不进 Git。以后搭配上身图在这里切换。

## 当前阶段

当前是朋友版衣柜的代码基线，品牌、路径和进度请按实际需要修改。
→ 状态与待改项见 [docs/06-当前进度.md](docs/06-当前进度.md)
→ 搭配页模特展示方案见 [docs/07-模特与搭配展示规划.md](docs/07-模特与搭配展示规划.md)

## 关键命令

```bash
# 激活虚拟环境（Git Bash）
source .venv/Scripts/activate

# 创建环境（首次）
py -3.11 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 运行程序
.venv/Scripts/python.exe main.py

# 打包程序
.venv/Scripts/pyinstaller.exe --noconfirm --onefile --windowed --name=Yelena的衣柜 ^
  --icon=web/assets/icon.ico --add-data "web;web" ^
  --collect-all webview --collect-all pythonnet --collect-all clr_loader main.py
```

## 远程仓库

`https://github.com/Y1221ting/yangjun-closes.git`（main 分支）

## 用户偏好

- 用户是编程小白，不懂代码
- 需要最终产物是可双击运行的 .exe
- 开发过程中需要清晰反馈进展
- 界面风格：蓝水彩夜空风（雾蓝、奶油、金色挂杆、幼圆标题；靠 `variables.css`
  变量 + `theme-yelena.css` 覆盖实现）
