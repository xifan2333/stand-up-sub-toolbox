import zipfile
import os
import re
import html
import webvtt
import pypandoc
import chardet
import tempfile
import ass
import pysrt
import datetime
from template import MarkdownTemplate, HTMLTemplate
from DrissionPage import ChromiumPage, ChromiumOptions
import requests
from rich.progress import Progress, BarColumn
from rich.console import Console
import argparse
import json
from collections import defaultdict
from opencc import OpenCC
import filecmp

cc = OpenCC("s2t")

banner = r"""
[blue]
   __________    ___  ____  _  __
  / __/_  __/___/ _ )/ __ \| |/_/
 _\ \  / / /___/ _  / /_/ />  <  
/___/ /_/     /____/\____/_/|_|  

[/blue]                                                                               
[red][b]Stand-up subtitles toolbox v1.0[/b][/red]
[green]author: @xifan[/green]

"""


class Toolbox:
    def __init__(self):
        self.chrome_path = "tools/chrome/chrome.exe"
        self.pandoc_path = "tools/pandoc/pandoc.exe"
        self.template_path = "templates"
        self.api_key = "4d81bcbc939fae61654a32969f4ca989"
        os.environ["PATH"] += os.pathsep + self.pandoc_path
        os.environ["PATH"] += os.pathsep + self.chrome_path
        self.console = Console()
        self.progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            "[progress.completed]{task.completed}/{task.total}",
            "{task.fields[filename]}",
            console=self.console,
        )
        self.task_states = {}
        self.batch_mode = False

    def save_task_state(self, task_id, completed_files):
        self.task_states[task_id] = completed_files
        with open("task_states.json", "w") as f:
            json.dump(self.task_states, f)

    def load_task_state(self, task_id):
        try:
            with open("task_states.json", "r") as f:
                self.task_states = json.load(f)
            return self.task_states.get(task_id, [])
        except FileNotFoundError:
            self.console.print("[red]未找到任务状态文件[/red]")
            return []

    def batch_unzip(self, zip_files, output_folder, resume=False):
        self.batch_mode = True
        task_id = "unzip"
        completed_files = self.load_task_state(task_id) if resume else []

        with self.progress:
            task = self.progress.add_task(
                "[green]📦 解压缩...", total=len(zip_files), filename=""
            )

            for zip_file in zip_files:
                self.progress.update(
                    task, filename=f"正在处理: {os.path.basename(zip_file)}"
                )
                if zip_file in completed_files:
                    self.progress.advance(task)
                    continue

                if self.unzip(zip_file, output_folder):
                    completed_files.append(zip_file)
                    self.save_task_state(task_id, completed_files)

                self.progress.advance(task)
        self.batch_mode = False

    def batch_convert(self, source_files, target_path, _format, resume=False):
        self.batch_mode = True
        task_id = f"convert_{_format}"
        completed_files = self.load_task_state(task_id) if resume else []

        with self.progress:
            task = self.progress.add_task(
                f"[blue]🔄 转换为 {_format}...", total=len(source_files), filename=""
            )

            for source_file in source_files:
                self.progress.update(
                    task, filename=f"正在处理: {os.path.basename(source_file)}"
                )
                if source_file in completed_files:
                    self.progress.advance(task)
                    continue

                self.convert(source_file, target_path, _format)
                completed_files.append(source_file)
                self.save_task_state(task_id, completed_files)

                self.progress.advance(task)
        self.batch_mode = False

    def batch_rename(self, input_paths, resume=False):
        self.batch_mode = True
        task_id = "rename"
        completed_files = self.load_task_state(task_id) if resume else []
        files_to_rename = []

        for input_path in input_paths:
            if os.path.isdir(input_path):
                files_to_rename.extend(
                    [
                        os.path.join(input_path, f)
                        for f in os.listdir(input_path)
                        if f.endswith((".vtt", ".srt", ".ass"))
                    ]
                )
            elif os.path.isfile(input_path) and input_path.endswith(
                (".vtt", ".srt", ".ass")
            ):
                files_to_rename.append(input_path)

        with self.progress:
            task = self.progress.add_task(
                "[cyan]✏️ 重命名...", total=len(files_to_rename), filename=""
            )

            for file in files_to_rename:
                self.progress.update(
                    task, filename=f"正在处理: {os.path.basename(file)}"
                )
                if file in completed_files:
                    self.progress.advance(task)
                    continue

                self.rename(file)
                completed_files.append(file)
                self.save_task_state(task_id, completed_files)

                self.progress.advance(task)
        self.batch_mode = False

    def diff(self, source_folder, target_folder, _format, resume=False):
        self.batch_mode = True
        task_id = "diff"
        completed_files = self.load_task_state(task_id) if resume else []

        dcmp = filecmp.dircmp(source_folder, target_folder)
        missing_files = [
            file for file in dcmp.left_only if file.endswith((".vtt", ".srt", ".ass"))
        ]

        if missing_files:
            self.console.print("[yellow][b]📋 以下文件在目标目录中缺失:[/b][/yellow]")
            for file in missing_files:
                if file in completed_files:
                    self.console.print(f"[blue]{file}[/blue] [green]✔️[/green]")
                else:
                    self.console.print(f"[yellow]{file}[/yellow] [red]❌[/red]")

            files_to_process = [
                file for file in missing_files if file not in completed_files
            ]

            if not files_to_process:
                self.console.print("[green]✅ 所有缺失文件已处理完毕。")
                return

            self.console.print("\n🤔 是否要转换这些文件? (y/n)", style="bold cyan")
            user_input = input().lower()

            if user_input != "y":
                self.console.print("❌ 操作已取消。", style="bold red")
                return
        else:
            self.console.print("[green]✅ 没有发现遗漏的文件。")
            return

        with self.progress:
            task = self.progress.add_task(
                "[cyan]🔍 比对并转换文件...", total=len(files_to_process), filename=""
            )

            for file in files_to_process:
                source_file = os.path.join(source_folder, file)
                self.progress.update(task, filename=f"正在处理: {file}")
                self.convert(source_file, target_folder, _format)  # 默认转换为 markdown
                completed_files.append(file)
                self.save_task_state(task_id, completed_files)
                self.progress.advance(task)

        self.batch_mode = False
        self.console.print(
            f"[green]🎉 完成比对和转换。共处理 {len(files_to_process)} 个文件。"
        )

    def unzip(self, zip_file_path, output_folder):
        try:
            file_name = os.path.basename(zip_file_path)
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(output_folder)
            if not self.batch_mode:
                self.console.print(
                    f"[green]成功解压文件 {file_name} 到 {output_folder}[/green]"
                )
            return True
        except Exception as e:
           
            self.console.print(f"[red]解压文件 {file_name} 时出错: {str(e)}[/red]")
            return False

    def rename(self, source_file):
        try:
            filename = os.path.basename(source_file)
            dirname = os.path.dirname(source_file)
            if (
                filename.endswith(".vtt")
                or filename.endswith(".srt")
                or filename.endswith(".ass")
            ):
                name, ext = os.path.splitext(filename)
                parts = name.split(".")

                lang_codes = [
                    part
                    for part in parts
                    if part in ["ENG", "CC", "FORCED", "CHS", "CHT", "Unknown", "SDH"]
                    or part.startswith(("en", "zh", "cmn", "yue"))
                ]

                if len(lang_codes) > 1 or "Unknown" in parts:
                    title = ".".join(
                        [
                            part
                            for part in parts
                            if part not in lang_codes and part != "Unknown"
                        ]
                    )
                    std_lang_code = ".".join(
                        [code for code in lang_codes if code != "Unknown"]
                    )
                    new_filename = f"{title}.{std_lang_code}{ext}"
                elif re.search(
                    r"\.(ENG\.CC|ENG\.FORCED|ENG\.SDH|ENG|CHS\.FORCED|CHS|CHT\.FORCED|CHT)$",
                    name,
                ):
                    if not self.batch_mode:
                        self.console.print(
                            f"[blue] 文件 '{filename}' 名称已标准化，跳过[/blue]"
                        )
                    return filename
                else:
                    lang_match = re.search(
                        r"(en(?:\[cc\]|-forced|-IN\[cc\]|-US|-GB)?|zh(?:-Hans|-Hant|-CN|-TW|-HK|-SG|-forced)?|cmn-(?:Hans|Hant)|yue-(?:Hans|Hant)|CHZ|ENG|CHS|CHT|CC|SDH)$",
                        name,
                    )
                    lang_code = lang_match.group(1) if lang_match else "Unknown"
                    title = re.sub(
                        r"\.(en(?:\[cc\]|-forced|-IN\[cc\]|-US|-GB)?|zh(?:-Hans|-Hant|-CN|-TW|-HK|-SG|-forced)?|cmn-(?:Hans|Hant)|yue-(?:Hans|Hant)|CHZ|ENG|CHS|CHT|CC|SDH)$",
                        "",
                        name,
                    )
                    title = re.sub(r"_+", ".", title)
                    title = re.sub(r"\.+", ".", title)
                    title = re.sub(r"\.(?:WEBRip|Netflix)", "", title)
                    lang_map = {
                        "en[cc]": "ENG",
                        "en-IN[cc]": "ENG",
                        "en-US": "ENG",
                        "en-GB": "ENG",
                        "zh-Hans": "CHS",
                        "zh-Hans-forced": "CHS",
                        "zh-Hant": "CHT",
                        "zh-Hant-forced": "CHT",
                        "zh-CN": "CHS",
                        "zh-TW": "CHT",
                        "zh-HK": "CHT",
                        "zh-SG": "CHS",
                        "zh": "CHS",
                        "cmn-Hans": "CHS",
                        "cmn-Hant": "CHT",
                        "yue-Hans": "CHS",
                        "yue-Hant": "CHT",
                        "en-forced": "ENG",
                        "en": "ENG",
                        "CHZ": "CHS",
                        "ENG": "ENG",
                        "CHS": "CHS",
                        "CHT": "CHT",
                        "CC": "CC",
                        "SDH": "SDH",
                    }
                    std_lang_code = lang_map.get(lang_code, "Unknown")
                    new_filename = f"{title}.{std_lang_code}{ext}"
                    os.rename(source_file, os.path.join(dirname, new_filename))

                if new_filename != filename:
                    if not self.batch_mode:
                        self.console.print(
                            f"[green]将'{filename}' 重命名为 '{new_filename}'[/green]"
                        )
                    return new_filename
                else:
                    if not self.batch_mode:
                        self.console.print(f"[blue]文件 '{filename}' 无需重命名[/blue]")
                    return filename
            else:
                if not self.batch_mode:
                    self.console.print(
                        f"[blue] 文件 '{filename}' 不是字幕文件，跳过[/blue]"
                    )
                return filename
        except Exception as e:
            if not self.batch_mode:
                self.console.print(f"[red] 重命名文件时出错: {str(e)}[/red]")
            return filename

    def _get_title(self, source_file):
        try:
            # 从文件名中提取可能的标题
            filename = os.path.splitext(os.path.basename(source_file))[0]
            language = self._get_lang_code(filename)
            filename = filename.split(f".{language}")[0]
            title = filename.replace(".", " ")

            base_url = "https://api.themoviedb.org/3"
            movie_search_url = f"{base_url}/search/movie"
            movie_params = {
                "api_key": self.api_key,
                "query": title,
                "language": "zh-CN",
            }
            movie_response = requests.get(movie_search_url, params=movie_params)
            movie_data = movie_response.json()
            tv_search_url = f"{base_url}/search/tv"
            tv_params = {"api_key": self.api_key, "query": title, "language": "zh-CN"}
            tv_response = requests.get(tv_search_url, params=tv_params)
            tv_data = tv_response.json()

            if movie_data.get("results") and movie_data["results"][0]:
                chinese_title = movie_data["results"][0].get("title", "")
                original_title = movie_data["results"][0].get("original_title", "")
                if language == "CHS":
                    return chinese_title
                elif language == "CHT":
                    chinese_title = cc.convert(chinese_title)
                    return chinese_title
                elif language == "ENG":
                    return original_title
            elif tv_data.get("results") and tv_data["results"][0]:
                chinese_title = tv_data["results"][0].get("name", "")
                original_title = tv_data["results"][0].get("original_name", "")
                if language == "CHS" or language == "CHT":
                    return chinese_title
                elif language == "ENG":
                    return original_title
            else:
                return title.replace(".", " ")

        except Exception as e:
            self.console.print(f"[red]获取标题时出错: {str(e)}[/red]")
            return title

    def _convert_charset(self, source_file: str):
        try:
            ext = os.path.splitext(source_file)[1]
            with open(source_file, "rb") as file:
                raw_data = file.read()
                result = chardet.detect(raw_data)
                source_encoding = result["encoding"]
            with open(source_file, "r", encoding=source_encoding) as sf:
                content = sf.read()

            with tempfile.NamedTemporaryFile(
                mode="w+", encoding="utf-8", delete=False, suffix=ext
            ) as temp_file:
                temp_file.write(content)
                if not self.batch_mode:
                    self.console.print(
                        f"[green]已将 {source_file} 编码 {source_encoding} 转换为utf-8[/green]"
                    )
                return temp_file.name
        except Exception as e:
            if not self.batch_mode:
                self.console.print(f"[red]转换编码时出错: {str(e)}[/red]")
            return ""

    def _convert_to_txt(self, source_file, target_path=None, temp=False):
        try:
            source_file = self._convert_charset(source_file)
            filename = f"{os.path.splitext(os.path.basename(source_file))[0]}.txt"
            file_extension = os.path.splitext(source_file)[1].lower()
            content = ""
            match file_extension:
                case ".vtt":
                    content = self._process_vtt(source_file)
                case ".srt":
                    content = self._process_srt(source_file)
                case ".ass":
                    content = self._process_ass(source_file)
                case _:
                    if not self.batch_mode:
                        self.console.print(
                            f"[red]不支持的文件格式: {file_extension}[/red]"
                        )
                    return ""
            if temp:
                with tempfile.NamedTemporaryFile(
                    mode="w+", encoding="utf-8", delete=False, suffix=".txt"
                ) as temp_file:
                    temp_file.write(content)
                    if not self.batch_mode:
                        self.console.print(
                            f"[green]{source_file} 转换为txt成功[/green]"
                        )
                    return temp_file.name
            else:
                if not target_path:
                    target_file = filename
                else:
                    target_file = os.path.join(target_path, filename)
                with open(target_file, "w", encoding="utf-8") as txt_file:
                    txt_file.write(content)
                    if not self.batch_mode:
                        self.console.print(
                            f"[green]{source_file} 转换为txt成功[/green]"
                        )
                    return target_file
        except Exception as e:
            if not self.batch_mode:
                self.console.print(
                    f"[red]处理文件 '{os.path.basename(source_file)}' 时出错: {str(e)}[/red]"
                )
            return ""

    def _process_vtt(self, source_file):
        try:
            
            content = ""
            for caption in webvtt.read(source_file):
                clean_text = self._clean_text(caption.text)
                if clean_text:
                    content += clean_text + "\n"
            return content
        except Exception as e:
            self.console.print(
                f"[red]处理 VTT 文件 '{os.path.basename(source_file)}' 时出错: {str(e)}[/red]"
            )
            return ""

    def _process_srt(self, source_file):
        try:
            subs = pysrt.open(source_file, encoding="utf-8")
            content = ""
            for sub in subs:
                clean_text = self._clean_text(sub.text)
                if clean_text:
                    content += clean_text + "\n"
            return content
        except Exception as e:
            self.console.print(
                f"[red]处理 SRT 文件 '{os.path.basename(source_file)}' 时出错: {str(e)}[/red]"
            )
            return ""

    def _process_ass(self, source_file):
        try:
            content = ""
            with open(source_file, encoding="utf-8") as ass_file:
                ass_data = ass.parse(ass_file)
            for event in ass_data.events:
                clean_text = self._clean_text(event.text)
                if clean_text:
                    content += clean_text + "\n"
            return content
        except Exception as e:
           
            self.console.print(
                f"[red]处理 ASS 文件 '{os.path.basename(source_file)}' 时出错: {str(e)}[/red]"
            )
            return ""

    def _clean_text(self, text):
        # 移除HTML实体和标签
        clean_text = html.unescape(text)
        clean_text = re.sub(r"<[^>]+>", "", clean_text)
        # 移除Unicode控制字符，包括LRM (U+200E)和RLM (U+200F)
        clean_text = re.sub(r"[\u200E\u200F]", "", clean_text)
        # 移除其他可能的特殊字符和空白
        clean_text = clean_text.strip()
        return clean_text

    def _convert_to_markdown(self, source_file, target_path=None, temp=False):
        txt_file = self._convert_to_txt(source_file, temp=True)
        filename = f"{os.path.splitext(os.path.basename(source_file))[0]}.md"
        if txt_file is None:
            return
        with open(txt_file, "r", encoding="utf-8") as txt:
            lines = txt.readlines()
            content = "".join([f"{line.strip()}  \n" for line in lines])

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = self._get_title(source_file)
        markdown_content = MarkdownTemplate.render(
            {"title": title, "timestamp": timestamp, "content": content}
        )
        if temp:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".md"
            ) as temp_md_file:
                temp_md_file.write(markdown_content.encode("utf-8"))
                if not self.batch_mode:
                    self.console.print(
                        f"[green]{source_file} 转换为markdown成功[/green]"
                    )
                return temp_md_file.name
        else:
            if not target_path:
                target_file = filename
            else:
                target_file = os.path.join(target_path, filename)
            with open(target_file, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content)
                if not self.batch_mode:
                    self.console.print(
                        f"[green]{source_file} 转换为markdown成功[/green]"
                    )
                return target_file

    def _convert_to_docx(self, source_file, target_path=None):
        filename = f"{os.path.splitext(os.path.basename(source_file))[0]}.docx"
        markdown_temp = self._convert_to_markdown(source_file, temp=True)
        if not markdown_temp:
            return

        if not target_path:
            target_file = filename
        else:
            target_file = os.path.join(target_path, filename)
        try:
            pypandoc.convert_file(
                markdown_temp,
                "docx",
                outputfile=target_file,
                extra_args=[
                    f"--reference-doc={os.path.join(self.template_path, 'template.docx')}"
                ],
                encoding="utf-8",
            )
            if not self.batch_mode:
                self.console.print(f"[green]{source_file} 转换为docx成功[/green]")
        finally:
            os.unlink(markdown_temp)

        return target_file

    def _convert_to_html(self, source_file, target_path=None, temp=False):
        txt_file = self._convert_to_txt(source_file, temp=True)
        filename = f"{os.path.splitext(os.path.basename(source_file))[0]}.html"
        if txt_file is None:
            return
        with open(txt_file, "r", encoding="utf-8") as txt_file:
            lines = txt_file.readlines()
            content = "".join([f"<p> {line.strip()} </p>" for line in lines])
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = self._get_title(source_file)
        html_content = HTMLTemplate.render(
            {"title": title, "timestamp": timestamp, "content": content}
        )
        if temp:
            with tempfile.NamedTemporaryFile(
                mode="w+", encoding="utf-8", delete=False, suffix=".html"
            ) as temp_file:
                temp_file.write(html_content)
                if not self.batch_mode:
                    self.console.print(f"[green]{source_file} 转换为html成功[/green]")
                return temp_file.name
        else:
            if not target_path:
                target_file = filename
            else:
                target_file = os.path.join(target_path, filename)
            with open(target_file, "w", encoding="utf-8") as html_file:
                html_file.write(html_content)
                if not self.batch_mode:
                    self.console.print(f"[green]{source_file} 转换为html成功[/green]")
                return target_file

    def _convert_to_pdf(self, source_file: str, target_path=None):
        filename = os.path.splitext(os.path.basename(source_file))[0]
        co = ChromiumOptions(read_file=False)
        co.set_paths(browser_path=self.chrome_path)
        co.headless(True)
        co.auto_port()
        page = ChromiumPage(addr_or_opts=co)
        html_temp = self._convert_to_html(source_file, temp=True)

        try:
            target_file = os.path.join(target_path, filename)
            page.get(f"file://{os.path.abspath(html_temp)}")
            main = page.ele("tag:main")
            main.wait.displayed()
            page.save(
                path=target_path if target_path else ".",
                name=filename,
                as_pdf=True,
                generateTaggedPDF=True,
                generateDocumentOutline=True,
                displayHeaderFooter=True,
                headerTemplate="<div></div>",
                footerTemplate='<div style="width:100%; text-align:center; font-size:10px;"><span class="pageNumber"></span>&nbsp;/&nbsp;<span class="totalPages"></span></div>',
            )
        except Exception as e:
            self.console.print(f"[red]转换PDF时出错: {str(e)}[/red]")
            return ""
        finally:
            page.quit()
            os.unlink(html_temp)
        return target_file

    def convert(self, source_file, target_path=None, _format=None):
        if _format is None:
            _format = "md"
        try:
            match _format:
                case "md":
                    self._convert_to_markdown(source_file, target_path)
                case "docx":
                    self._convert_to_docx(source_file, target_path)
                case "html":
                    self._convert_to_html(source_file, target_path)
                case "pdf":
                    self._convert_to_pdf(source_file, target_path)
                case "txt":
                    self._convert_to_txt(source_file, target_path)
                case _:
                    if not self.batch_mode:
                        self.console.print(f"[red]不支持的文件格式: {_format}[/red]")
            if not self.batch_mode:
                self.console.print(f"成功将 {source_file} 转换为 {_format}")
        except Exception as e:
            self.console.print(f"[red]转换文件 {source_file} 时出错: {str(e)}")

    def clean(self, input_folder, resume=False):
        self.batch_mode = True
        task_id = "clean"
        completed_folders = self.load_task_state(task_id) if resume else []

        with self.progress:
            task = self.progress.add_task(
                "[magenta]🧹 清理文件...", total=1, filename=""
            )

            if input_folder in completed_folders:
                self.progress.update(task, advance=1)
                return

            self.progress.update(
                task, filename=f"[magenta]正在处理: {input_folder}[/magenta]"
            )

            files = [
                f
                for f in os.listdir(input_folder)
                if os.path.isfile(os.path.join(input_folder, f))
            ]
            groups = defaultdict(list)

            for file in files:
                name, ext = os.path.splitext(file)
                base_name = re.sub(r"\.(CHS|CHT|ENG|CC|FORCED|SDH).*$", "", name)
                groups[base_name].append(file)

            for base_name, group in groups.items():
                if len(group) > 1:
                    self._clean_group(input_folder, group)

            completed_folders.append(input_folder)
            self.save_task_state(task_id, completed_folders)
            self.progress.update(task, advance=1)

        self.batch_mode = False

    def _clean_group(self, folder, group):
        lang_files = {"CHS": [], "CHT": [], "ENG": [], "Unknown": []}

        for file in group:
            lang = self._get_lang_code(file)
            lang_files[lang].append(file)

        for lang, files in lang_files.items():
            if files:
                # 保留每种语言中最大的文件
                largest_file = max(
                    files, key=lambda f: os.path.getsize(os.path.join(folder, f))
                )
                for file in files:
                    if file != largest_file:
                        os.remove(os.path.join(folder, file))
                        self.console.print(f"[red]删除文件: {file}[/red]")

    def _get_lang_code(self, filename):
        match = re.search(r"\.(CHS|CHT|ENG)", filename)
        return match.group(1) if match else "Unknown"


def main():
    console = Console()
    console.print(banner)
    console.print("👋 欢迎使用字幕工具箱 CLI", style="bold blue")
    console.print("❓ 使用 -h 或 --help 查看帮助信息\n", style="bold blue")
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")

    # 解压命令
    unzip_parser = subparsers.add_parser("unzip", aliases=["u"], help="批量解压文件")
    unzip_parser.add_argument(
        "-i", "--input", nargs="+", required=True, help="输入zip文件或目录"
    )
    unzip_parser.add_argument("-o", "--output", required=True, help="输出目录")
    unzip_parser.add_argument("-r", "--resume", action="store_true", help="断点续传")

    # 转换命令
    convert_parser = subparsers.add_parser(
        "convert", aliases=["co"], help="批量转换文件"
    )
    convert_parser.add_argument(
        "-i", "--input", nargs="+", required=True, help="输入文件或目录"
    )
    convert_parser.add_argument("-o", "--output", required=True, help="输出目录")
    convert_parser.add_argument(
        "-f",
        "--format",
        choices=["md", "docx", "html", "pdf", "txt"],
        default="md",
        help="转换格式",
    )
    convert_parser.add_argument("-r", "--resume", action="store_true", help="断点续传")

    # 重命名命令
    rename_parser = subparsers.add_parser(
        "rename", aliases=["r"], help="批量重命名文件"
    )
    rename_parser.add_argument(
        "-i", "--input", nargs="+", required=True, help="输入文件或目录"
    )
    rename_parser.add_argument("-r", "--resume", action="store_true", help="断点续传")

    # 清理命令
    clean_parser = subparsers.add_parser(
        "clean", aliases=["cl"], help="清理重复的字幕文件"
    )
    clean_parser.add_argument("-i", "--input", required=True, help="输入目录")
    clean_parser.add_argument("-r", "--resume", action="store_true", help="断点续传")

    # 比对命令
    diff_parser = subparsers.add_parser(
        "diff", aliases=["d"], help="比对并转换缺失的字幕文件"
    )
    diff_parser.add_argument("-i", "--input", required=True, help="输入目录")
    diff_parser.add_argument("-o", "--output", required=True, help="输出目录")
    diff_parser.add_argument(
        "-f",
        "--format",
        choices=["md", "docx", "html", "pdf", "txt"],
        default="md",
        help="转换格式",
    )
    diff_parser.add_argument("-r", "--resume", action="store_true", help="断点续传")

    args = parser.parse_args()

    toolbox = Toolbox()

    try:
        if args.action in ["unzip", "u"]:
            zip_files = []
            for input_path in args.input:
                if os.path.isdir(input_path):
                    zip_files.extend(
                        [
                            os.path.join(input_path, f)
                            for f in os.listdir(input_path)
                            if f.endswith(".zip")
                        ]
                    )
                else:
                    zip_files.append(input_path)
            toolbox.batch_unzip(zip_files, args.output, args.resume)
        elif args.action in ["convert", "co"]:
            source_files = []
            for input_path in args.input:
                if os.path.isdir(input_path):
                    source_files.extend(
                        [
                            os.path.join(input_path, f)
                            for f in os.listdir(input_path)
                            if f.endswith((".vtt", ".srt", ".ass"))
                        ]
                    )
                else:
                    source_files.append(input_path)
            toolbox.batch_convert(source_files, args.output, args.format, args.resume)
        elif args.action in ["rename", "r"]:
            toolbox.batch_rename(args.input, args.resume)
        elif args.action in ["clean", "cl"]:
            toolbox.clean(args.input, args.resume)
        elif args.action in ["diff", "d"]:
            toolbox.diff(args.input, args.output, args.format, args.resume)
    except KeyboardInterrupt:
        console.print("\n👋 程序已退出，Bye！", style="bold yellow")
    except Exception as e:
        console.print(f"\n❌ 哎呀，出错了: {str(e)}", style="bold red")
    finally:
        if not args.action:
            parser.print_help()
        else:
            console.print("\n👋 Bye！", style="bold blue")


if __name__ == "__main__":
    main()
