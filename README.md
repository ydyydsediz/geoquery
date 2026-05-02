# GeoQuery - 地名经纬度批量查询工具

批量查询地名经纬度，上传 Excel/CSV 文件，自动调用高德地图 API 获取坐标并导出结果。

## 功能特点

- **批量查询**：一次上传上百条地名，自动逐条查询经纬度
- **文件格式**：支持 `.xlsx`、`.xls`、`.csv` 三种格式
- **实时进度**：查询过程中实时显示当前进度和每条结果
- **结果导出**：查询完成后可直接下载包含「地名 + 经度 + 纬度」的结果文件
- **开箱即用**：提供 Windows 独立可执行文件，无需安装 Python 环境

## 快速开始

### 方式一：直接运行（推荐）

从 [Releases](https://github.com/ydyydsediz/geoquery/releases) 页面下载最新版 `GeoQuery-windows.zip`，解压后运行 `GeoQuery.exe`，浏览器会自动打开操作页面。

### 方式二：从源码运行

```bash
# 克隆项目
git clone https://github.com/ydyydsediz/geoquery.git
cd geoquery

# 安装依赖
pip install -r requirements.txt

# 运行
python app.py
```

浏览器访问 `http://127.0.0.1:5000` 即可使用。

## 使用说明

### 第一步：获取高德 API Key

1. 打开 [高德开放平台](https://lbs.amap.com/)，点击右上角**注册/登录**（如已有账号直接登录）
2. 登录后进入**控制台**，点击左侧菜单 **「应用管理」→「我的应用」**
3. 点击**「创建新应用」**，填写应用名称（如 `GeoQuery`）和应用类型，点击「创建」
4. 在新建的应用卡片中，点击**「添加」**按钮（🔑 图标）添加 Key
5. 在弹窗中：
   - **服务平台**选择 **「Web 服务」**（重要！不是 Web 端(JS API)）
   - 填写一个 Key 名称
   - 点击「提交」
6. 创建成功后即可看到生成的 **Key 字符串**（类似 `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`），复制备用

> **提示**：高德 Web 服务 API 每日有免费配额（个人开发者通常足够使用），超出后需申请提升配额或等待次日重置。

### 第二步：准备数据文件

创建一个 Excel（`.xlsx`）或 CSV（`.csv`）文件，**第一列**填写需要查询的地名，无需表头：

| A列 |
|-----|
| 北京市天安门广场 |
| 上海市东方明珠 |
| 杭州市西湖 |
| 成都市春熙路 |

### 第三步：查询

1. 运行 `GeoQuery.exe`（或 `python app.py`），浏览器会自动打开操作页面
2. 将第一步复制的 API Key 粘贴到页面输入框中
3. 拖拽或点击上传第二步准备的数据文件
4. 点击**「开始查询」**，页面会实时显示查询进度

### 第四步：下载结果

查询完成后，页面会显示成功/失败的统计信息，点击**「下载结果」**按钮即可保存结果文件，内容包含三列：地名、经度、纬度。

## 项目结构

```
geoquery/
├── .github/
│   └── workflows/
│       └── release.yml   # GitHub Actions 自动打包发布
├── templates/
│   └── index.html        # 前端页面
├── .gitignore
├── app.py                # 后端主程序（Flask）
├── build.bat             # 一键打包脚本
├── GeoQuery.spec         # PyInstaller 打包配置
├── README.md
└── requirements.txt      # Python 依赖
```

## 打包为可执行文件

```bash
# 一键打包（Windows）
build.bat
```

打包产物位于 `dist/GeoQuery/` 目录，运行 `GeoQuery.exe` 即可启动。

## 依赖项

| 依赖        | 用途                      |
| ----------- | ------------------------- |
| Flask       | Web 框架                  |
| requests    | HTTP 请求（调用高德 API） |
| pandas      | 数据读写                  |
| openpyxl    | Excel 文件支持            |
| PyInstaller | 打包为可执行文件          |

## 许可证

MIT License
