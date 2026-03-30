import tkinter as tk
from tkinter import messagebox, filedialog
import os
import json
from datetime import datetime

DATA_FILE = "notes_data.json"

def load_notes():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_notes(notes):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

class NotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova笔记 📝")
        self.root.geometry("700x600")
        self.root.configure(bg="#1a1a2e")
        
        notes = load_notes()
        
        # 顶部标题
        tk.Label(root, text="📝 Nova笔记", font=("Arial", 20, "bold"),
                bg="#1a1a2e", fg="#eee").pack(pady=10)
        
        # 输入区域
        input_frame = tk.Frame(root, bg="#1a1a2e")
        input_frame.pack(pady=10, fill="x", padx=20)
        
        self.entry = tk.Entry(input_frame, font=("Arial", 14), bg="#16213e", fg="#eee",
                             insertbackground="#eee", relief="flat", bd=5)
        self.entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.entry.bind("<Return>", lambda e: self.add_note())
        
        tk.Button(input_frame, text="添加笔记", command=self.add_note,
                bg="#e94560", fg="white", relief="flat", font=("Arial", 12),
                cursor="hand2", padx=15).pack(side="right", padx=(10, 0))
        
        # 笔记列表
        list_frame = tk.Frame(root, bg="#1a1a2e")
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.canvas = tk.Canvas(list_frame, bg="#1a1a2e", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.list_container = tk.Frame(self.canvas, bg="#1a1a2e")
        
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((0, 0), window=self.list_container, anchor="nw")
        
        self.list_container.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.notes = notes
        self.refresh_list()
    
    def refresh_list(self):
        for widget in self.list_container.winfo_children():
            widget.destroy()
        
        for i, note in enumerate(self.notes):
            self.create_note_card(i, note)
    
    def create_note_card(self, index, note):
        card = tk.Frame(self.list_container, bg="#16213e", relief="flat", bd=0)
        card.pack(fill="x", pady=5, ipady=8)
        
        time_str = note.get("time", "")[:16]
        tk.Label(card, text=f"🕒 {time_str}", font=("Arial", 8),
                bg="#16213e", fg="#888").pack(anchor="w", padx=10, pady=(5,0))
        
        tk.Label(card, text=note["text"], font=("Arial", 12),
                bg="#16213e", fg="#eee", wraplength=550, justify="left").pack(
                    anchor="w", padx=10, pady=2)
        
        btn_frame = tk.Frame(card, bg="#16213e")
        btn_frame.pack(anchor="e", padx=10, pady=(0,5))
        
        tk.Button(btn_frame, text="🗑 删除", command=lambda i=index: self.delete_note(i),
                 bg="#e94560", fg="white", relief="flat", font=("Arial", 9),
                 cursor="hand2", padx=10).pack(side="right")
    
    def add_note(self):
        text = self.entry.get().strip()
        if not text:
            return
        
        note = {"text": text, "time": datetime.now().isoformat()}
        self.notes.insert(0, note)
        save_notes(self.notes)
        self.entry.delete(0, tk.END)
        self.refresh_list()
    
    def delete_note(self, index):
        if messagebox.askyesno("确认删除", "确定删除这条笔记吗？"):
            self.notes.pop(index)
            save_notes(self.notes)
            self.refresh_list()

if __name__ == "__main__":
    root = tk.Tk()
    app = NotesApp(root)
    root.mainloop()
