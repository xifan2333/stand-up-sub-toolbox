# 字幕工具箱 (Subtitle Toolbox)

字幕工具箱是一个功能强大的命令行工具，用于处理和转换各种格式的字幕文件。它提供了多种实用功能，包括批量解压、格式转换、重命名、清理和比对等。

## 功能特点

- 批量解压ZIP文件
- 将字幕文件转换为多种格式（Markdown、DOCX、HTML、PDF、TXT）
- 批量重命名字幕
- 清理重复的字幕文件
- 比对并转换缺失的字幕文件
- 支持断点续传

## 安装

1. 确保您的系统已安装[rye](https://rye-up.com/)。
2. 克隆此仓库或下载源代码。
3. 在项目目录中运行以下命令安装依赖：

```bash
rye sync
或者
pip install -r requirements.txt
```

注意：请在根目录下创建 tools 文件夹，并将需要用到的工具放在该文件夹下。
路径为：

- pandoc `tools/pandoc/pandoc.exe`
- chrome `tools/chrome/chrome.exe`


## 使用方法

```

   __________    ___  ____  _  __
  / __/_  __/___/ _ )/ __ \| |/_/
 _\ \  / / /___/ _  / /_/ />  <
/___/ /_/     /____/\____/_/|_|


Stand-up subtitles toolbox v1.0
author: @xifan


👋 欢迎使用字幕工具箱 CLI
❓ 使用 -h 或 --help 查看帮助信息
usage: toolbox.py [-h] {unzip,u,convert,co,rename,r,clean,cl,diff,d} ...

positional arguments:
  {unzip,u,convert,co,rename,r,clean,cl,diff,d}
    unzip (u)           批量解压文件
    convert (co)        批量转换文件
    rename (r)          批量重命名文件
    clean (cl)          清理重复的字幕文件
    diff (d)            比对并转换缺失的字幕文件

options:
  -h, --help            show this help message and exit
```

### 批量解压ZIP文件

```bash
python toolbox.py unzip -i 放压缩文件的文件夹 -o 要解压到的文件夹
比如：
python toolbox.py unzip -i ./zip -o ./unzip
```

### 批量转换字幕文件

```bash
python toolbox.py convert -i 放字幕文件的文件夹 -o 要转换到的文件夹 -f 要转换的格式 -r 是否断点续传
比如：
python toolbox.py convert -i ./md -o ./docx -f docx -r
```

### 批量重命名字幕文件

```bash
python toolbox.py rename -i 放字幕文件的文件夹
比如：
python toolbox.py rename -i ./srt
```

### 清理重复的字幕文件

```bash
python toolbox.py clean -i 放字幕文件的文件夹
比如：
python toolbox.py clean -i ./srt
```

### 比对并转换缺失的字幕文件

```bash
python toolbox.py diff -i 放字幕文件的文件夹 -o 要转换到的文件夹 -f 要转换的格式 -r 是否断点续传
比如：
python toolbox.py diff -i ./md -o ./pdf -f pdf -r
```