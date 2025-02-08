import os
import time
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import tkinter as tk
from tkinter import filedialog, ttk


class RepoMonitor(FileSystemEventHandler):
    def __init__(self, gui):
        self.gui = gui

    def on_modified(self, event):
        if not event.is_directory:
            self.gui.schedule_refresh()

    def on_created(self, event):
        self.gui.schedule_refresh()

    def on_deleted(self, event):
        self.gui.schedule_refresh()


class GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Repo Monitor")
        self.geometry("500x500")
        self.path = filedialog.askdirectory(title="Select the repository to monitor")
        self.check_vars = {}
        self.check_buttons = {}
        self.refresh_scheduled = False

        self.create_widgets()
        self.refresh_files(initial=True)

    def create_widgets(self):
        self.frame = tk.Frame(self)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.frame)
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.loading_label = tk.Label(self, text="", fg="green")
        self.loading_label.pack(side="bottom")

    def refresh_files(self, initial=False):
        new_files = set()

        for root, dirs, files in os.walk(self.path):
            # Remove hidden directories (those starting with a dot)
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file == 'transcribe.txt':
                    continue
                full_path = os.path.join(root, file)
                new_files.add(full_path)

        # Add new files
        for file_path in new_files:
            if file_path not in self.check_vars:
                var = tk.BooleanVar(value=True)
                display_name = os.path.relpath(file_path, self.path)
                chk = tk.Checkbutton(
                    self.scrollable_frame,
                    text=display_name,
                    variable=var,
                    command=self.write_to_file
                )
                chk.pack(anchor='w')
                self.check_vars[file_path] = var
                self.check_buttons[file_path] = chk

        # Remove checkboxes for files that no longer exist
        for file_path in list(self.check_vars.keys()):
            if file_path not in new_files:
                self.check_buttons[file_path].destroy()
                del self.check_vars[file_path]
                del self.check_buttons[file_path]

        self.write_to_file()

    def schedule_refresh(self):
        if not self.refresh_scheduled:
            self.refresh_scheduled = True
            self.after(1000, self.refresh_files)

    def write_to_file(self):
        self.loading_label.config(text="Processing...")
        try:
            with open(os.path.join(self.path, 'transcribe.txt'), 'w') as f:
                for file_path, var in self.check_vars.items():
                    if var.get():
                        corrected_path = file_path.replace("\\", "/")
                        f.write(f"{corrected_path}\n")
                        with open(file_path, 'r') as content_file:
                            f.write(content_file.read() + "\n\n")
        except Exception as e:
            print("Error:", e)
        self.loading_label.config(text="")
        self.refresh_scheduled = False


def monitor_directory(gui):
    event_handler = RepoMonitor(gui)
    observer = Observer()
    # Schedule the observer to watch the directory recursively
    observer.schedule(event_handler, gui.path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    gui = GUI()

    thread = Thread(target=monitor_directory, args=(gui,))
    thread.daemon = True
    thread.start()

    gui.mainloop()