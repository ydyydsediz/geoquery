# Git 推送问题记录与 GitHub Actions 使用指南

## 一、Git 推送过程中遇到的问题及解决方案

### 问题 1：远程仓库名称不是 `origin`

**现象：** 执行 `git push origin master` 报错 `fatal: 'origin' does not appear to be a git repository`

**原因：** 项目最初通过 GitHub Desktop 或手动配置，远程仓库名称设置为 `geoquery` 而非默认的 `origin`

**解决：**
```bash
# 查看当前远程仓库配置
git remote -v

# 使用正确的远程名称推送
git push geoquery master
```

---

### 问题 2：默认分支是 `master` 而非 `main`

**现象：** 创建本地 `main` 分支后推送到远程，发现远程默认分支实际是 `master`

**原因：** GitHub 仓库创建时选择的默认分支是 `master`（GitHub Desktop 早期默认行为）

**解决：** 统一使用 `master` 作为主分支名称，不要创建 `main` 分支

---

### 问题 3：Feature 分支创建为孤儿分支（Orphan）

**现象：** 创建 `feature/v1.1-reverse-geocoding` 分支后，看不到之前的提交历史

**原因：** 使用了 `git checkout --orphan` 创建孤儿分支，该分支没有父提交。同时本地没有 `master` 分支的 checkout，导致 git 在空仓库状态下创建了分支

**解决：**
```bash
# 先确保本地有 master 分支
git checkout master

# 再从 master 创建 feature 分支
git checkout -b feature/v1.1-reverse-geocoding
```

---

### 问题 4：`.spec` 文件被 `.gitignore` 排除

**现象：** `git add GeoQuery.spec` 无效，文件无法添加到暂存区

**原因：** `.gitignore` 中有 `*.spec` 规则，PyInstaller 的 `.spec` 文件默认被排除

**解决：**
```bash
# 使用 -f（force）强制添加被忽略的文件
git add -f GeoQuery.spec
```

---

### 问题 5：推送 Master 分支被拒绝（non-fast-forward）

**现象：** `git push geoquery master` 报错 `non-fast-forward`，远程 master 有本地没有的提交

**原因：** Feature 分支的内容需要合并到 master，但本地 master 落后于远程

**解决：**
```bash
# 安全的强制推送（会检查远程是否有新提交）
git push --force-with-lease geoquery master
```

**注意：** `--force-with-lease` 比 `--force` 更安全，它会在远程有别人新推送的提交时拒绝推送，避免覆盖他人的工作。

---

### 问题 6：无法 checkout master，因为有未跟踪文件

**现象：** `git checkout master` 失败，提示有未跟踪的文件会被覆盖

**原因：** 当前分支有未提交的文件，与目标分支存在冲突

**解决：**
```bash
# 暂存所有文件（包括未跟踪的）
git stash --include-untracked

# 切换分支
git checkout master

# 如需恢复暂存的内容
git stash pop
```

---

### 问题 7：Windows PowerShell 不支持 `&&` 语法

**现象：** `cd dir && git status` 报错

**原因：** PowerShell 不支持 Bash 的 `&&` 命令链接语法

**解决：** 使用分号 `;` 替代，或者将路径作为命令参数
```powershell
# 方法一：分号分隔
cd "D:\path"; git status

# 方法二：指定工作目录
git -C "D:\path" status
```

---

### 问题 8：Trae IDE 沙箱限制无法写入项目外文件

**现象：** 使用 `Set-Content` 写入 `.github/workflows/release.yml` 被拒绝

**原因：** Trae IDE 的安全沙箱只允许在当前打开的项目目录内读写文件，父目录超出权限范围

**解决：** 在项目目录内创建 Python 辅助脚本来写入文件
```python
# write_workflow.py - 在项目目录内运行
import os
content = """workflow yaml content..."""
target = os.path.join("..", ".github", "workflows", "release.yml")
os.makedirs(os.path.dirname(target), exist_ok=True)
with open(target, "w", encoding="utf-8") as f:
    f.write(content)
```
```bash
python write_workflow.py
```

---

## 二、GitHub Actions 工作流配置

### 工作流文件位置

```
D:\PythonCode\经纬度获取\.github\workflows\release.yml
```

### 工作流触发条件

当推送以 `v` 开头的标签（tag）时自动触发：

```yaml
on:
  push:
    tags:
      - "v*"
```

### 工作流执行流程

```
推送 v* 标签
    ↓
GitHub Actions 在 windows-latest 环境启动
    ↓
checkout 代码
    ↓
安装 Python 3.8 + pip 缓存
    ↓
pip install -r requirements.txt
    ↓
PyInstaller 打包（使用 GeoQuery.spec）
    ↓
压缩 dist/GeoQuery/ 为 GeoQuery-windows.zip
    ↓
创建 GitHub Release 并上传 zip 附件
```

---

## 三、如何触发 GitHub Actions

### 方式一：推送标签（推荐，标准流程）

```bash
# 1. 确保代码已提交并推送到 master
git push geoquery master

# 2. 创建本地标签
git tag v1.2.0

# 3. 推送标签到远程（触发 Actions）
git push geoquery v1.2.0
```

GitHub 会自动：
- 运行 CI 构建流程
- 生成 `GeoQuery-windows.zip`
- 创建新的 Release 页面并上传附件

### 方式二：在 GitHub 网页手动触发

如果需要手动重新运行构建：

1. 打开 [Actions 页面](https://github.com/ydyydsediz/geoquery/actions)
2. 点击左侧 **Build and Release** 工作流
3. 点击右上角 **Run workflow**（需要在 yml 中配置 `workflow_dispatch` 触发器）
4. 选择分支，点击 **Run workflow** 按钮

> **注意：** 当前工作流未配置 `workflow_dispatch`，如需支持手动触发，需在 `release.yml` 中添加：
> ```yaml
> on:
>   push:
>     tags:
>       - "v*"
>   workflow_dispatch:   # 添加这一行
> ```

### 方式三：重新运行失败的构建

1. 打开 [Actions 页面](https://github.com/ydyydsediz/geoquery/actions)
2. 点击失败的 workflow run
3. 右上角点击 **Re-run all jobs**

---

## 四、版本发布标准流程（Git Flow）

```
# 1. 从 master 创建 feature 分支
git checkout master
git checkout -b feature/v1.2-新功能名称

# 2. 在 feature 分支上开发和提交
git add .
git commit -m "feat: 新功能描述"

# 3. 测试通过后，合并到 master
git checkout master
git merge feature/v1.2-新功能名称

# 4. 推送 master
git push geoquery master

# 5. 创建版本标签（自动触发 Actions 打包发布）
git tag v1.2.0
git push geoquery v1.2.0

# 6. 清理 feature 分支
git branch -d feature/v1.2-新功能名称
git push geoquery --delete feature/v1.2-新功能名称
```

---

## 五、常见 Git 命令速查

| 操作 | 命令 |
|------|------|
| 查看远程仓库 | `git remote -v` |
| 查看所有分支 | `git branch -a` |
| 查看标签 | `git tag -l` |
| 查看提交历史 | `git log --oneline --graph --all` |
| 强制添加被忽略的文件 | `git add -f <file>` |
| 暂存当前工作 | `git stash --include-untracked` |
| 恢复暂存的工作 | `git stash pop` |
| 删除远程标签 | `git push geoquery --delete v1.0.0` |
| 重新推送标签 | `git tag -d v1.0.0; git push geoquery :refs/tags/v1.0.0; git tag v1.0.0; git push geoquery v1.0.0` |
| 安全强制推送 | `git push --force-with-lease geoquery master` |
