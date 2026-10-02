#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MP4 无损裁剪工具（ffmpeg 流拷贝）。"""

import os
import re
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

VIDEOS_BASE_DIR = r"F:\lym_things\Videos"
SUPPORTED_GAMES = [
    "Apex Legends",
    "Counter-strike 2",
    "Helltaker",
    "How to Fish",
]

COLORS = {
    "bg": "#14171c",
    "surface": "#1e2329",
    "surface_elevated": "#262c34",
    "border": "#3a424f",
    "text": "#eef0f2",
    "text_muted": "#8b939e",
    "accent": "#c82a2a",
    "accent_light": "#e84545",
    "success": "#45c88a",
    "danger": "#e07070",
    "log_bg": "#0f1216",
    "log_fg": "#c8cdd3",
}
UI_FONT_MONO = ("Consolas", 10)

_escaped_games = [re.escape(g) for g in SUPPORTED_GAMES]
DVR_FILENAME_RE = re.compile(
    rf"^({'|'.join(_escaped_games)}) (\d{{4}}\.\d{{2}}\.\d{{2}} - \d{{2}}\.\d{{2}}\.\d{{2}}\.\d{{2}})\.DVR\.mp4$"
)


def setup_theme(root: tk.Tk) -> ttk.Style:
    """界面主题与 ttk 样式。"""
    global UI_FONT_MONO
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    root.configure(bg=COLORS["bg"])

    font_ui = ("Microsoft YaHei UI", 9)
    font_ui_bold = ("Microsoft YaHei UI", 9, "bold")
    UI_FONT_MONO = ("Consolas", 10)
    if os.name == "nt":
        import tkinter.font as tkfont

        for family in ("Cascadia Mono", "Consolas", "Courier New"):
            if family.lower() in {f.lower() for f in tkfont.families(root)}:
                UI_FONT_MONO = (family, 10)
                break

    style.configure(
        ".", background=COLORS["bg"], foreground=COLORS["text"], font=font_ui
    )
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Surface.TFrame", background=COLORS["surface"])
    style.configure("Card.TFrame", background=COLORS["surface_elevated"])
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure(
        "Muted.TLabel", background=COLORS["bg"], foreground=COLORS["text_muted"]
    )
    style.configure(
        "Card.TLabel", background=COLORS["surface_elevated"], foreground=COLORS["text"]
    )
    style.configure(
        "CardMuted.TLabel",
        background=COLORS["surface_elevated"],
        foreground=COLORS["text_muted"],
    )
    style.configure(
        "HeaderTitle.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=("Microsoft YaHei UI", 16, "bold"),
    )
    style.configure(
        "HeaderSubtitle.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text_muted"],
        font=font_ui,
    )
    style.configure(
        "Section.TLabelframe", background=COLORS["surface"], foreground=COLORS["text"]
    )
    style.configure(
        "Section.TLabelframe.Label",
        background=COLORS["surface"],
        foreground=COLORS["accent_light"],
        font=("Microsoft YaHei UI", 10, "bold"),
    )
    style.configure(
        "Card.TLabelframe",
        background=COLORS["surface_elevated"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=COLORS["surface_elevated"],
        foreground=COLORS["accent_light"],
        font=font_ui_bold,
    )

    entry_opts = {
        "fieldbackground": COLORS["surface"],
        "foreground": COLORS["text"],
        "insertcolor": COLORS["text"],
        "bordercolor": COLORS["border"],
        "lightcolor": COLORS["border"],
        "darkcolor": COLORS["border"],
        "padding": 4,
    }
    style.configure("TEntry", **entry_opts)
    style.configure("Time.TEntry", **entry_opts, width=4, justify="center")
    style.configure(
        "TButton",
        background=COLORS["surface_elevated"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        padding=(12, 6),
        font=font_ui,
    )
    style.map(
        "TButton",
        background=[("active", COLORS["border"]), ("pressed", COLORS["border"])],
        foreground=[("disabled", COLORS["text_muted"])],
    )
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground="#ffffff",
        bordercolor=COLORS["accent"],
        padding=(20, 10),
        font=font_ui_bold,
    )
    style.map(
        "Accent.TButton",
        background=[
            ("active", COLORS["accent_light"]),
            ("pressed", COLORS["accent_light"]),
        ],
        foreground=[("disabled", "#aaaaaa")],
    )
    style.configure(
        "Danger.TButton",
        background=COLORS["surface"],
        foreground=COLORS["danger"],
        bordercolor=COLORS["border"],
        padding=(10, 4),
    )
    style.map("Danger.TButton", background=[("active", COLORS["surface_elevated"])])
    style.configure(
        "Vertical.TScrollbar",
        background=COLORS["surface"],
        troughcolor=COLORS["bg"],
        bordercolor=COLORS["bg"],
        arrowcolor=COLORS["text_muted"],
    )
    style.configure(
        "StatusOk.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["success"],
        font=font_ui_bold,
    )
    style.configure(
        "StatusErr.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["danger"],
        font=font_ui_bold,
    )
    return style


def check_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


_DURATION_EPSILON = 0.001


def _subprocess_no_window_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _ffprobe_durations(filepath: str, entries: str) -> list[float] | None:
    """读取 ffprobe 输出的时长列表。ffprobe 缺失或执行失败时返回 None。"""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        entries,
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        filepath,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_subprocess_no_window_flags(),
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None

    values: list[float] = []
    for line in (result.stdout or "").splitlines():
        text = line.strip()
        if not text or text.upper() == "N/A":
            continue
        try:
            value = float(text)
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return values


def probe_media_duration(filepath: str) -> float | None:
    """返回媒体时长（秒）。优先容器时长，否则取各流时长的最大值。"""
    if shutil.which("ffprobe") is None:
        return None
    format_durations = _ffprobe_durations(filepath, "format=duration")
    if format_durations:
        return format_durations[0]
    if format_durations is None:
        return None
    stream_durations = _ffprobe_durations(filepath, "stream=duration")
    if not stream_durations:
        return None
    return max(stream_durations)


def time_exceeds_duration(seconds: int, duration: float) -> bool:
    return seconds > duration + _DURATION_EPSILON


def seconds_from_hms(hours: str, minutes: str, seconds: str) -> int:
    h = int(hours.strip() or "0")
    m = int(minutes.strip() or "0")
    s = int(seconds.strip() or "0")
    return h * 3600 + m * 60 + s


def format_time_label(total_seconds: int) -> str:
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    parts = [f"{h}h"] if h else []
    parts.extend([f"{m}m", f"{s}s"])
    return "".join(parts)


def format_duration_display(total_seconds: int) -> str:
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_dvr_info(filepath: str) -> tuple[str, str] | None:
    """从 DVR 文件名提取 (游戏名, 时间戳)，不匹配返回 None。"""
    match = DVR_FILENAME_RE.match(os.path.basename(filepath))
    if match:
        return match.group(1), match.group(2)
    return None


def normalize_output_filename(name: str, start_sec: int, end_sec: int) -> str:
    if not name or not name.strip():
        base = f"{format_time_label(start_sec)}-{format_time_label(end_sec)}"
    else:
        base = os.path.basename(name.strip())
    if base.lower().endswith(".mp4"):
        base = base[:-4]
    return base + ".mp4"


def append_dvr_timestamp(filename: str, timestamp: str) -> str:
    """在文件名（不含扩展名）后附加 DVR 录制时间戳。"""
    base = filename[:-4] if filename.lower().endswith(".mp4") else filename
    return f"{base}_{timestamp}.mp4"


class ClipSegmentFrame(ttk.LabelFrame):
    """单条裁剪片段。"""

    def __init__(self, parent, segment_index: int, on_delete_callback, **kwargs):
        super().__init__(
            parent,
            text=f"片段 {segment_index}",
            style="Card.TLabelframe",
            padding=(14, 10),
            **kwargs,
        )
        self.segment_index = segment_index
        self.on_delete_callback = on_delete_callback
        self._build_ui()

    def set_segment_index(self, index: int) -> None:
        self.segment_index = index
        self.configure(text=f"片段 {index}")

    @staticmethod
    def _pack_hms_inputs(parent: ttk.Frame, hour_var, min_var, sec_var) -> None:
        for var, unit in ((hour_var, "时"), (min_var, "分"), (sec_var, "秒")):
            ttk.Entry(parent, textvariable=var, width=4, style="Time.TEntry").pack(
                side=tk.LEFT
            )
            padx = (2, 6) if unit != "秒" else (2, 0)
            ttk.Label(parent, text=unit, style="CardMuted.TLabel").pack(
                side=tk.LEFT, padx=padx
            )

    def _build_ui(self):
        self.start_hour = tk.StringVar(value="0")
        self.start_min = tk.StringVar(value="0")
        self.start_sec = tk.StringVar(value="0")
        self.end_hour = tk.StringVar(value="0")
        self.end_min = tk.StringVar(value="0")
        self.end_sec = tk.StringVar(value="0")
        self.output_name = tk.StringVar()

        row = 0
        ttk.Label(self, text="起始", style="Card.TLabel").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 6)
        )
        start_frame = ttk.Frame(self, style="Card.TFrame")
        start_frame.grid(row=row, column=1, sticky=tk.W, padx=(0, 20))
        self._pack_hms_inputs(
            start_frame, self.start_hour, self.start_min, self.start_sec
        )

        ttk.Label(self, text="结束", style="Card.TLabel").grid(
            row=row, column=2, sticky=tk.W, padx=(0, 6)
        )
        end_frame = ttk.Frame(self, style="Card.TFrame")
        end_frame.grid(row=row, column=3, sticky=tk.W)
        self._pack_hms_inputs(end_frame, self.end_hour, self.end_min, self.end_sec)

        ttk.Button(
            self, text="删除", style="Danger.TButton", command=self._on_delete
        ).grid(row=row, column=4, sticky=tk.E, padx=(16, 0))

        row = 1
        ttk.Label(self, text="文件名", style="Card.TLabel").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 6), pady=(10, 0)
        )
        ttk.Entry(self, textvariable=self.output_name).grid(
            row=row, column=1, columnspan=3, sticky=tk.EW, pady=(10, 0)
        )
        ttk.Label(self, text="可留空", style="CardMuted.TLabel").grid(
            row=row, column=4, sticky=tk.W, pady=(10, 0)
        )
        self.columnconfigure(1, weight=1)

    def _on_delete(self):
        if self.on_delete_callback:
            self.on_delete_callback(self)

    def get_times(self) -> tuple[int, int]:
        start = seconds_from_hms(
            self.start_hour.get(), self.start_min.get(), self.start_sec.get()
        )
        end = seconds_from_hms(
            self.end_hour.get(), self.end_min.get(), self.end_sec.get()
        )
        return start, end

    def get_output_filename(self, start_sec: int, end_sec: int) -> str:
        return normalize_output_filename(self.output_name.get(), start_sec, end_sec)

    def validate(self, index: int) -> str | None:
        for label, var_hour, var_min, var_sec in (
            ("起始", self.start_hour, self.start_min, self.start_sec),
            ("结束", self.end_hour, self.end_min, self.end_sec),
        ):
            for part_name, var in (("时", var_hour), ("分", var_min), ("秒", var_sec)):
                val = var.get().strip()
                if not val:
                    continue
                if not re.fullmatch(r"\d+", val):
                    return f"片段 {index + 1}：{label}{part_name}须为非负整数"

        try:
            start, end = self.get_times()
        except ValueError:
            return f"片段 {index + 1}：时间无效"

        if end <= start:
            return f"片段 {index + 1}：结束须大于起始"
        return None


class VideoCutterApp:
    """主窗口。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("APEX Legends高光裁剪工具")
        self.root.minsize(900, 600)
        self.root.geometry("940x720")

        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=os.path.join(VIDEOS_BASE_DIR, SUPPORTED_GAMES[0]))
        self.append_dvr_time = tk.BooleanVar(value=False)
        self._dvr_info: tuple[str, str] | None = None
        self._user_changed_output = False
        self.clip_frames: list[ClipSegmentFrame] = []
        self._processing = False
        self._ffmpeg_ok = check_ffmpeg_available()

        self._build_ui()
        self._add_clip()
        self.input_path.trace_add("write", self._on_input_path_changed)
        self._update_dvr_append_state()

        if not self._ffmpeg_ok:
            messagebox.showerror(
                "ffmpeg 不可用",
                "未找到 ffmpeg，请安装并加入 PATH 后重试。",
            )

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=(16, 14))
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 14))
        title_block = ttk.Frame(header)
        title_block.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(
            title_block, text="APEX Legends高光裁剪", style="HeaderTitle.TLabel"
        ).pack(anchor=tk.W)
        ttk.Label(title_block, text="MP4 无损", style="HeaderSubtitle.TLabel").pack(
            anchor=tk.W, pady=(2, 0)
        )
        status_style = "StatusOk.TLabel" if self._ffmpeg_ok else "StatusErr.TLabel"
        status_text = "ffmpeg 就绪" if self._ffmpeg_ok else "ffmpeg 未找到"
        ttk.Label(header, text=status_text, style=status_style).pack(
            side=tk.RIGHT, anchor=tk.NE
        )

        input_frame = ttk.LabelFrame(
            main, text="输入", style="Section.TLabelframe", padding=10
        )
        input_frame.pack(fill=tk.X, pady=(0, 10))
        row_in = ttk.Frame(input_frame, style="Surface.TFrame")
        row_in.pack(fill=tk.X)
        ttk.Entry(row_in, textvariable=self.input_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        ttk.Button(row_in, text="浏览", command=self._browse_input).pack(side=tk.RIGHT)

        output_frame = ttk.LabelFrame(
            main, text="输出", style="Section.TLabelframe", padding=10
        )
        output_frame.pack(fill=tk.X, pady=(0, 10))
        row_out = ttk.Frame(output_frame, style="Surface.TFrame")
        row_out.pack(fill=tk.X)
        ttk.Entry(row_out, textvariable=self.output_dir).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        ttk.Button(row_out, text="浏览", command=self._browse_output).pack(
            side=tk.RIGHT
        )

        self.append_dvr_frame = ttk.Frame(output_frame, style="Surface.TFrame")
        self.append_dvr_frame.pack(fill=tk.X, pady=(8, 0))
        self.chk_append_dvr = ttk.Checkbutton(
            self.append_dvr_frame,
            text="附加录制时间到文件名",
            variable=self.append_dvr_time,
            command=self._on_append_dvr_toggle,
        )
        self.chk_append_dvr.pack(side=tk.LEFT)

        clips_outer = ttk.LabelFrame(
            main, text="片段", style="Section.TLabelframe", padding=10
        )
        clips_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        list_area = ttk.Frame(clips_outer, style="Surface.TFrame")
        list_area.pack(fill=tk.BOTH, expand=True)
        self.clips_canvas = tk.Canvas(
            list_area, highlightthickness=0, bg=COLORS["surface"], bd=0
        )
        clips_scroll = ttk.Scrollbar(
            list_area, orient=tk.VERTICAL, command=self.clips_canvas.yview
        )
        self.clips_inner = ttk.Frame(self.clips_canvas, style="Surface.TFrame")

        self.clips_inner.bind(
            "<Configure>",
            lambda e: self.clips_canvas.configure(
                scrollregion=self.clips_canvas.bbox("all")
            ),
        )
        self._clips_window = self.clips_canvas.create_window(
            (0, 0), window=self.clips_inner, anchor=tk.NW
        )
        self.clips_canvas.configure(yscrollcommand=clips_scroll.set)
        self.clips_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        clips_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.clips_canvas.bind("<Configure>", self._on_clips_canvas_configure)
        self.clips_canvas.bind("<Enter>", self._bind_mousewheel)
        self.clips_canvas.bind("<Leave>", self._unbind_mousewheel)

        ttk.Button(clips_outer, text="添加片段", command=self._add_clip).pack(
            anchor=tk.W, pady=(8, 0)
        )

        action_frame = ttk.Frame(main)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        self.btn_start = ttk.Button(
            action_frame,
            text="开始裁剪",
            style="Accent.TButton",
            command=self._start_cutting,
        )
        self.btn_start.pack(side=tk.LEFT)
        ttk.Button(action_frame, text="重置", command=self._reset_ui).pack(
            side=tk.RIGHT
        )

        log_frame = ttk.LabelFrame(
            main, text="日志", style="Section.TLabelframe", padding=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_inner = tk.Frame(log_frame, bg=COLORS["log_bg"])
        log_inner.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(
            log_inner,
            height=8,
            state=tk.DISABLED,
            wrap=tk.WORD,
            font=UI_FONT_MONO,
            bg=COLORS["log_bg"],
            fg=COLORS["log_fg"],
            insertbackground=COLORS["text"],
            relief=tk.FLAT,
            padx=8,
            pady=8,
            borderwidth=0,
            highlightthickness=0,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("ok", foreground=COLORS["success"])
        self.log_text.tag_configure("err", foreground=COLORS["danger"])
        self.log_text.tag_configure("info", foreground=COLORS["text_muted"])

    def _on_clips_canvas_configure(self, event):
        self.clips_canvas.itemconfig(self._clips_window, width=event.width)

    def _bind_mousewheel(self, _event):
        self.clips_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.clips_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.clips_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, _event):
        self.clips_canvas.unbind_all("<MouseWheel>")
        self.clips_canvas.unbind_all("<Button-4>")
        self.clips_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self.clips_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.clips_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.clips_canvas.yview_scroll(1, "units")

    def _reset_ui(self):
        if self._processing:
            messagebox.showwarning("提示", "正在裁剪中，请稍后再试。")
            return

        self.input_path.set("")
        self.output_dir.set(os.path.join(VIDEOS_BASE_DIR, SUPPORTED_GAMES[0]))
        self.append_dvr_time.set(False)
        self._user_changed_output = False

        for frame in self.clip_frames:
            frame.destroy()
        self.clip_frames.clear()
        self._add_clip()

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self.clips_canvas.yview_moveto(0)
        self._update_dvr_append_state()

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="选择视频",
            filetypes=[("MP4", "*.mp4"), ("全部", "*.*")],
        )
        if path:
            self.input_path.set(path)

    def _on_input_path_changed(self, *_args):
        self._update_dvr_append_state()

    def _update_dvr_append_state(self):
        path = self.input_path.get().strip()
        self._dvr_info = parse_dvr_info(path) if path else None

        if self._dvr_info:
            game, _timestamp = self._dvr_info
            if not self._user_changed_output:
                self.output_dir.set(os.path.join(VIDEOS_BASE_DIR, game))
            self.chk_append_dvr.configure(state=tk.NORMAL)
            self.append_dvr_frame.unbind("<Button-1>")
            self.chk_append_dvr.unbind("<Button-1>")
        else:
            self.append_dvr_time.set(False)
            self.chk_append_dvr.configure(state=tk.DISABLED)
            self.append_dvr_frame.bind("<Button-1>", self._on_append_dvr_blocked_click)
            self.chk_append_dvr.bind("<Button-1>", self._on_append_dvr_blocked_click)

    def _on_append_dvr_blocked_click(self, _event=None):
        supported = "、".join(SUPPORTED_GAMES)
        messagebox.showwarning("提示", f"仅支持以下游戏的 DVR 视频：{supported}")

    def _on_append_dvr_toggle(self):
        if not self._dvr_info:
            self.append_dvr_time.set(False)
            supported = "、".join(SUPPORTED_GAMES)
            messagebox.showwarning("提示", f"仅支持以下游戏的 DVR 视频：{supported}")

    def _resolve_output_filename(
        self, frame: ClipSegmentFrame, start_sec: int, end_sec: int
    ) -> str:
        filename = frame.get_output_filename(start_sec, end_sec)
        if self.append_dvr_time.get() and self._dvr_info:
            filename = append_dvr_timestamp(filename, self._dvr_info[1])
        return filename

    def _browse_output(self):
        path = filedialog.askdirectory(
            title="选择文件夹", initialdir=self.output_dir.get()
        )
        if path:
            self.output_dir.set(path)
            self._user_changed_output = True

    def _refresh_segment_indices(self) -> None:
        for i, frame in enumerate(self.clip_frames, start=1):
            frame.set_segment_index(i)

    def _add_clip(self):
        index = len(self.clip_frames) + 1
        frame = ClipSegmentFrame(
            self.clips_inner, segment_index=index, on_delete_callback=self._remove_clip
        )
        frame.pack(fill=tk.X, padx=4, pady=6)
        self.clip_frames.append(frame)
        self.clips_inner.update_idletasks()
        self.clips_canvas.configure(scrollregion=self.clips_canvas.bbox("all"))
        self.clips_canvas.yview_moveto(1.0)

    def _remove_clip(self, frame: ClipSegmentFrame):
        if len(self.clip_frames) <= 1:
            messagebox.showwarning("提示", "至少保留一个片段。")
            return
        frame.destroy()
        self.clip_frames.remove(frame)
        self._refresh_segment_indices()
        self.clips_inner.update_idletasks()
        self.clips_canvas.configure(scrollregion=self.clips_canvas.bbox("all"))

    def _log(self, message: str, tag: str | None = None):
        if tag is None:
            stripped = message.strip()
            if stripped.startswith("✓"):
                tag = "ok"
            elif stripped.startswith("✗"):
                tag = "err"
            elif message.startswith("  ") or message.startswith("="):
                tag = "info"

        def append():
            self.log_text.configure(state=tk.NORMAL)
            if tag:
                self.log_text.insert(tk.END, message + "\n", tag)
            else:
                self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

        self.root.after(0, append)

    def _set_ui_busy(self, busy: bool):
        def update():
            self.btn_start.configure(state=tk.DISABLED if busy else tk.NORMAL)
            if busy:
                self.chk_append_dvr.configure(state=tk.DISABLED)
            else:
                self._update_dvr_append_state()

        self.root.after(0, update)

    def _validate_all(self) -> bool:
        if not check_ffmpeg_available():
            messagebox.showerror("错误", "未找到 ffmpeg。")
            return False

        input_file = self.input_path.get().strip()
        if not input_file:
            messagebox.showerror("错误", "请选择输入文件。")
            return False
        if not os.path.isfile(input_file):
            messagebox.showerror("错误", f"文件不存在：\n{input_file}")
            return False
        if not input_file.lower().endswith(".mp4"):
            messagebox.showwarning("提示", "可能不是 MP4，仍将尝试处理。")

        out_dir = self.output_dir.get().strip()
        if not out_dir:
            messagebox.showerror("错误", "请指定输出目录。")
            return False
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
                self._log(f"已创建目录：{out_dir}")
            except OSError as e:
                messagebox.showerror("错误", f"无法创建目录：\n{out_dir}\n{e}")
                return False

        if not self.clip_frames:
            messagebox.showerror("错误", "请添加至少一个片段。")
            return False

        for i, frame in enumerate(self.clip_frames):
            if err := frame.validate(i):
                messagebox.showerror("错误", err)
                return False

        if shutil.which("ffprobe") is None:
            messagebox.showerror("错误", "未找到 ffprobe。")
            return False
        duration = probe_media_duration(input_file)
        if duration is None:
            messagebox.showerror("错误", "无法读取视频时长。")
            return False
        for i, frame in enumerate(self.clip_frames):
            start_sec, end_sec = frame.get_times()
            for label, value in (("起始", start_sec), ("结束", end_sec)):
                if time_exceeds_duration(value, duration):
                    messagebox.showerror(
                        "错误",
                        f"片段 {i + 1}：{label}时间 {format_duration_display(value)} "
                        f"超过视频长度 {format_duration_display(int(duration))}",
                    )
                    return False
        return True

    def _run_ffmpeg_cut(
        self, input_file: str, output_file: str, start_sec: int, end_sec: int
    ) -> tuple[bool, str]:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_sec),
            "-to",
            str(end_sec),
            "-i",
            input_file,
            "-map",
            "0",
            "-c",
            "copy",
            "-map_metadata",
            "0",
            "-avoid_negative_ts",
            "make_zero",
            output_file,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_subprocess_no_window_flags(),
            )
        except FileNotFoundError:
            return False, "未找到 ffmpeg。"
        except Exception as e:
            return False, str(e)

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return False, f"ffmpeg 错误 ({result.returncode})\n{detail}"
        return True, ""

    def _start_cutting(self):
        if self._processing or not self._validate_all():
            return
        self._processing = True
        self._set_ui_busy(True)
        self._log("=" * 40)
        self._log("开始裁剪…")
        threading.Thread(target=self._cut_worker, daemon=True).start()

    def _cut_worker(self):
        input_file = self.input_path.get().strip()
        out_dir = self.output_dir.get().strip()
        total = len(self.clip_frames)
        ok_count = fail_count = 0

        try:
            for i, frame in enumerate(self.clip_frames):
                start_sec, end_sec = frame.get_times()
                filename = self._resolve_output_filename(frame, start_sec, end_sec)
                output_path = os.path.join(out_dir, filename)

                self._log(
                    f"\n[{i + 1}/{total}] {os.path.basename(input_file)}"
                    f"\n  {format_duration_display(start_sec)} → {format_duration_display(end_sec)}"
                    f"\n  {output_path}"
                )
                self._log("  处理中…", tag="info")

                success, msg = self._run_ffmpeg_cut(
                    input_file, output_path, start_sec, end_sec
                )
                if success:
                    self._log(f"  ✓ {filename}")
                    ok_count += 1
                else:
                    self._log(f"  ✗ {msg}")
                    fail_count += 1

            self._log(f"\n完成：成功 {ok_count}，失败 {fail_count}")
            if fail_count == 0 and ok_count > 0:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo("完成", f"已裁剪 {ok_count} 个片段。"),
                )
            elif fail_count > 0:
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "部分失败", f"成功 {ok_count}，失败 {fail_count}，详见日志。"
                    ),
                )
        except Exception as e:
            self._log(f"\n错误：{e}")
            self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
        finally:
            self._processing = False
            self._set_ui_busy(False)


def main():
    root = tk.Tk()
    try:
        setup_theme(root)
    except tk.TclError:
        pass
    VideoCutterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
