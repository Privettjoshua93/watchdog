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

    def on_any_event(self, event):
        if not event.src_path.endswith('transcribe.txt'):
            self.gui.schedule_refresh()


class GUI(tk.Tk):
    BINARY_EXTENSIONS = {'.exe', '.dll', '.so', '.bin', '.jpg', '.jpeg', '.png',
                         '.gif', '.mp3', '.mp4', '.avi', '.mov', '.pdf', '.zip',
                         '.tar', '.gz', '.7z', '.pyc'}

    def __init__(self):
        super().__init__()
        self.title("Repo Monitor")
        self.geometry("800x600")
        self.configure(bg='#2e2e2e')

        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Treeview',
                        background='#2e2e2e',
                        foreground='white',
                        fieldbackground='#2e2e2e',
                        highlightthickness=0,
                        bd=0,
                        font=('Arial', 10))
        style.configure('Treeview.Heading',
                        background='#2e2e2e',
                        foreground='white',
                        font=('Arial', 10, 'bold'))
        style.map('Treeview',
                  background=[('selected', '#3e3e3e')],
                  foreground=[('selected', 'white')])

        self.path = filedialog.askdirectory(title="Select the repository to monitor")
        if not self.path:
            self.destroy()
            return

        self.refresh_scheduled = False
        self.selected_files = set()

        self.create_widgets()
        self.populate_tree()
        self.refresh_tree()

    def create_widgets(self):
        self.tree_frame = tk.Frame(self, bg='#2e2e2e')
        self.tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(self.tree_frame, show='tree', selectmode='none')
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        self.vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.vsb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=self.vsb.set)

        self.tree.bind('<<TreeviewOpen>>', self.on_open_event)
        self.tree.tag_bind('file', '<Button-1>', self.on_click_file)
        self.tree.tag_configure('selected', background='#3e3e3e', foreground='white')

        self.loading_label = tk.Label(self, text="", fg="green", bg='#2e2e2e')
        self.loading_label.pack(side="bottom")

    def is_visible(self, path):
        return not os.path.basename(path).startswith('.')

    def is_binary_file(self, filename):
        return os.path.splitext(filename)[1].lower() in self.BINARY_EXTENSIONS

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.insert_node('', self.path)

    def insert_node(self, parent, abspath):
        text = os.path.basename(abspath) or abspath
        if os.path.isdir(abspath):
            node = self.tree.insert(parent, 'end', text=text, open=False, values=(abspath,), tags=('folder',))
            self.tree.insert(node, 'end')
        else:
            node = self.tree.insert(parent, 'end', text=text, open=False, values=(abspath,), tags=('file',))
        return node

    def on_open_event(self, event):
        node = self.tree.focus()
        self.on_open_node(node)

    def on_open_node(self, node):
        item_values = self.tree.item(node, 'values')
        if not item_values:
            return

        abspath = item_values[0]
        self.tree.delete(*self.tree.get_children(node))

        try:
            for p in sorted(os.listdir(abspath)):
                p_abspath = os.path.join(abspath, p)
                if self.is_visible(p_abspath):
                    child_node = self.insert_node(node, p_abspath)
                    if os.path.isfile(p_abspath) and p_abspath in self.selected_files:
                        self.tree.item(child_node, tags=('file', 'selected'))
        except PermissionError:
            pass

    def on_click_file(self, event):
        item = self.tree.identify_row(event.y)
        if item and 'file' in self.tree.item(item, 'tags'):
            abspath = self.tree.item(item, 'values')[0]
            if abspath in self.selected_files:
                self.selected_files.remove(abspath)
                self.tree.item(item, tags=('file',))
            else:
                self.selected_files.add(abspath)
                self.tree.item(item, tags=('file', 'selected'))
            self.write_to_file()
            return "break"

    def refresh_tree(self):
        opened_paths = set()

        def save_state(node):
            item_values = self.tree.item(node, 'values')
            if item_values:
                abspath = item_values[0]
                if self.tree.item(node, 'open'):
                    opened_paths.add(abspath)
            for child in self.tree.get_children(node):
                save_state(child)

        save_state('')

        self.populate_tree()

        def restore_state(node):
            item_values = self.tree.item(node, 'values')
            if item_values:
                abspath = item_values[0]
                if abspath in opened_paths:
                    self.tree.item(node, open=True)
                    self.on_open_node(node)
                if abspath in self.selected_files:
                    self.tree.item(node, tags=('file', 'selected'))
            for child in self.tree.get_children(node):
                restore_state(child)

        restore_state('')

        self.refresh_scheduled = False

    def schedule_refresh(self):
        if not self.refresh_scheduled:
            self.refresh_scheduled = True
            self.after(1000, self.refresh_tree)

    def write_to_file(self):
        self.loading_label.config(text="Processing...")
        output_path = os.path.join(self.path, 'transcribe.txt')

        selected_files = list(self.selected_files)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for full_path in selected_files:
                    corrected_path = full_path.replace("\\", "/")
                    f.write(f"{corrected_path}\n")
                    try:
                        with open(full_path, 'r', encoding='utf-8') as content_file:
                            f.write(content_file.read() + "\n\n")
                    except (FileNotFoundError, UnicodeDecodeError) as e:
                        print(f"Error processing {full_path}: {e}")
            self.loading_label.config(text="")
        except Exception as e:
            print(f"Write error: {e}")
            self.loading_label.config(text="Error")

    def on_closing(self):
        self.destroy()


def monitor_directory(gui):
    event_handler = RepoMonitor(gui)
    observer = Observer()
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
    if gui.path:
        thread = Thread(target=monitor_directory, args=(gui,))
        thread.daemon = True
        thread.start()

        gui.protocol("WM_DELETE_WINDOW", gui.on_closing)
        gui.mainloop()