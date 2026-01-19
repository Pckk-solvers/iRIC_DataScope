from __future__ import annotations

import multiprocessing as mp
from multiprocessing.synchronize import Event as MpEvent
import sys
from pathlib import Path


def _splash_worker(done: MpEvent, splash_path: Path) -> None:
    try:
        import tkinter as tk
    except Exception:
        return

    root = tk.Tk()
    root.withdraw()

    splash = tk.Toplevel(root)
    splash.withdraw()
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)

    image = None
    if splash_path.is_file():
        try:
            image = tk.PhotoImage(file=str(splash_path))
        except Exception:
            image = None

    if image is None:
        splash.destroy()
        root.destroy()
        return

    label = tk.Label(splash, image=image, borderwidth=0, highlightthickness=0)
    label.pack()
    splash.update_idletasks()
    width = image.width()
    height = image.height()
    x = (splash.winfo_screenwidth() - width) // 2
    y = (splash.winfo_screenheight() - height) // 2
    splash.geometry(f"{width}x{height}+{x}+{y}")
    splash.deiconify()

    def _poll() -> None:
        if done.is_set():
            splash.destroy()
            root.destroy()
            return
        root.after(100, _poll)

    root.after(100, _poll)
    root.mainloop()


def _resolve_splash_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        return base / "iRIC_DataScope" / "assets" / "splash.png"
    return Path(__file__).resolve().parent / "iRIC_DataScope" / "assets" / "splash.png"


def main() -> None:
    mp.freeze_support()
    from iRIC_DataScope.app import main as app_main

    if getattr(sys, "frozen", False):
        app_main(show_splash=False)
        return

    done = mp.Event()
    splash_path = _resolve_splash_path()
    splash_proc = mp.Process(
        target=_splash_worker,
        args=(done, splash_path),
        daemon=True,
    )
    splash_proc.start()

    def _close_splash() -> None:
        if not done.is_set():
            done.set()

    try:
        app_main(show_splash=False, on_ready=_close_splash)
    finally:
        _close_splash()
        if splash_proc.is_alive():
            splash_proc.join(timeout=1.0)


if __name__ == "__main__":
    main()
