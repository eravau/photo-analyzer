import base64
import json
import requests
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, scrolledtext
from dataclasses import dataclass, fields
from typing import Optional, List, Any
import io

# Optional dependencies
try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import rawpy
    import imageio.v2 as imageio
except ImportError:
    rawpy = None
    imageio = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

# --- Tooltip helper ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, "bbox") else (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("tahoma", "9", "normal")
        )
        label.pack(ipadx=4)

    def hide(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

@dataclass
class OllamaResponse:
    model: str
    created_at: str
    response: str
    done: bool
    done_reason: Optional[str] = None
    context: Optional[List[Any]] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None

class OllamaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Photo analyzer - Caption & Evaluation")
        self.geometry("1200x800")  # Wider window
        self.resizable(False, False)

        self.image_path = None
        self.image_b64 = None
        self.preview_imgtk = None

        self.model_var = tk.StringVar(value="llava")
        self.mode_var = tk.StringVar(value="caption")

        self.create_widgets()
        self.make_drag_and_drop_work()

    def create_widgets(self):
        # Main container with two columns
        main_frame = tk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        main_frame.columnconfigure(0, weight=0, minsize=420)
        main_frame.columnconfigure(1, weight=1)

        # --- Left column: controls ---
        left_frame = tk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))

        # Title
        title = tk.Label(left_frame, text="Photo Analyzer", font=("Segoe UI", 20, "bold"))
        title.pack(pady=(12, 0))

        subtitle = tk.Label(
            left_frame,
            text="Generate Instagram captions, hashtags, or photo critiques using Ollama AI models.",
            font=("Segoe UI", 11)
        )
        subtitle.pack(pady=(0, 10))

        # Image selection frame
        img_frame = ttk.LabelFrame(left_frame, text="1. Select Image", padding=(10, 8))
        img_frame.pack(fill='x', pady=8)

        self.img_label = ttk.Label(
            img_frame,
            text="Drag & drop an image here or click 'Select Image'"
        )
        self.img_label.pack(fill='x', pady=(0, 4))

        btn_select = ttk.Button(img_frame, text="Select Image", command=self.select_image)
        btn_select.pack(pady=2)
        ToolTip(btn_select, "Open a file dialog to select an image file.")

        # Reserve space for preview using a fixed-size frame
        preview_frame = tk.Frame(img_frame, width=180, height=260)
        preview_frame.pack(pady=4)
        preview_frame.pack_propagate(False)

        self.preview_label = ttk.Label(preview_frame)
        self.preview_label.pack(expand=True)

        # Model and mode frame
        options_frame = ttk.LabelFrame(left_frame, text="2. Choose Model & Mode", padding=(10, 8))
        options_frame.pack(fill='x', pady=8)

        model_frame = ttk.Frame(options_frame)
        model_frame.pack(fill='x', pady=2)
        ttk.Label(model_frame, text="Model:").pack(side='left')
        model_options = ["gemma3", "llava"]
        model_menu = ttk.OptionMenu(model_frame, self.model_var, self.model_var.get(), *model_options)
        model_menu.pack(side='left', padx=10)
        ToolTip(model_menu, "Choose the Ollama model to use for analysis.")

        mode_frame = ttk.Frame(options_frame)
        mode_frame.pack(fill='x', pady=2)
        ttk.Label(mode_frame, text="Mode:").pack(side='left')
        modes = [("Instagram Caption", "caption"), ("Photo Evaluation", "evaluation")]
        for text, val in modes:
            rb = ttk.Radiobutton(mode_frame, text=text, variable=self.mode_var, value=val)
            rb.pack(side='left', padx=10)
            ToolTip(rb, f"Switch to {text.lower()} mode.")

        # Show the prompt being used
        self.prompt_display = tk.Label(left_frame, text="", wraplength=400, justify='left', fg="#555")
        self.prompt_display.pack(fill='x', padx=4, pady=(2, 8))

        # Prompt frame
        prompt_frame = ttk.LabelFrame(left_frame, text="3. Custom Prompt (optional)", padding=(10, 8))
        prompt_frame.pack(fill='x', pady=8)
        self.prompt_entry = ttk.Entry(prompt_frame, width=80)
        self.prompt_entry.pack(fill='x', padx=2, pady=2)
        ToolTip(self.prompt_entry, "Enter a custom prompt for the AI model (leave blank for default).")

        # Generate and progress
        action_frame = ttk.Frame(left_frame)
        action_frame.pack(fill='x', pady=(8, 0))

        self.btn_generate = ttk.Button(action_frame, text="Generate", command=self.on_generate)
        self.btn_generate.pack(side='left', padx=(0, 10))
        ToolTip(self.btn_generate, "Send the image and prompt to Ollama and generate a response.")

        self.progress = ttk.Label(action_frame, text="", foreground="green")
        self.progress.pack(side='left', padx=4)

        self.btn_copy = ttk.Button(
            action_frame,
            text="Copy to Clipboard",
            command=self.copy_to_clipboard,
            state='disabled'
        )
        self.btn_copy.pack(side='right')
        ToolTip(self.btn_copy, "Copy the generated response to the clipboard.")

        # --- Right column: output ---
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding=(10, 8))
        output_frame.grid(row=0, column=1, sticky='nsew')
        output_frame.pack_propagate(True)

        self.output_box = scrolledtext.ScrolledText(
            output_frame,
            height=10,
            wrap='word',
            font=("Consolas", 11)
        )
        self.output_box.pack(fill='both', expand=True)

        # Bind events to update prompt display
        self.prompt_entry.bind("<KeyRelease>", lambda e: self.update_prompt_display())
        self.mode_var.trace_add("write", lambda *a: self.update_prompt_display())

        # Initialize the prompt display
        self.update_prompt_display()

    def make_drag_and_drop_work(self):
        def drop(event):
            files = self.tk.splitlist(event.data)
            if files:
                filepath = files[0]
                if filepath.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".cr3")):
                    self.load_image(filepath)
                else:
                    messagebox.showerror("Invalid file", "Please drop a valid image file.")
            return "break"

        self.img_label.drop_target_register = getattr(self.img_label, "drop_target_register", lambda *a: None)
        self.img_label.drop_target_register('DND_Files')
        self.img_label.dnd_bind = getattr(self.img_label, "dnd_bind", lambda *a: None)
        self.img_label.dnd_bind('<<Drop>>', drop)

    def select_image(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.cr3")]
        )
        if filepath:
            self.load_image(filepath)

    def load_image(self, path):
        self.image_path = path
        self.img_label.config(text=f"Loaded image: {path}")
        try:
            img_bytes = None
            if path.lower().endswith(".cr3"):
                if rawpy is None or imageio is None:
                    messagebox.showerror(
                        "Missing dependency",
                        "rawpy and imageio are required for CR3 support.\nInstall with: pip install rawpy imageio"
                    )
                    self.image_b64 = None
                    self.show_preview(None)
                    return
                with rawpy.imread(path) as raw:
                    rgb = raw.postprocess()
                buf = io.BytesIO()
                imageio.imwrite(buf, rgb, format='jpeg')
                buf.seek(0)
                img_bytes = buf.getvalue()
                self.image_b64 = base64.b64encode(img_bytes).decode("utf-8")
            else:
                with open(path, "rb") as f:
                    img_bytes = f.read()
                    self.image_b64 = base64.b64encode(img_bytes).decode("utf-8")
            self.show_preview(img_bytes)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image:\n{e}")
            self.image_b64 = None
            self.show_preview(None)

    def show_preview(self, img_bytes):
        if Image is None or ImageTk is None:
            self.preview_label.config(text="Pillow not installed, preview unavailable.", image='')
            return
        if img_bytes is None:
            self.preview_label.config(image='', text="No preview available.")
            self.preview_imgtk = None
            return
        try:
            img = Image.open(io.BytesIO(img_bytes))
            img.thumbnail((180, 260))
            self.preview_imgtk = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_imgtk, text='')
        except Exception as e:
            self.preview_label.config(text=f"Preview error: {e}", image='')
            self.preview_imgtk = None

    def update_prompt_display(self, *args):
        prompt_text = self.prompt_entry.get().strip()
        mode = self.mode_var.get()
        if not prompt_text:
            if mode == "caption":
                prompt_text = (
                    "Generate an Instagram caption and hashtags for this photo. "
                    "Focus on mood and storytelling. Keep it concise and engaging."
                )
            elif mode == "evaluation":
                prompt_text = (
                    "Critique this image from a photographic perspective. "
                    "Focus on composition, mood, lighting, and storytelling."
                )
        self.prompt_display.config(text=f"Prompt to be sent:\n{prompt_text}")

    def on_generate(self):
        if not self.image_b64:
            messagebox.showwarning("No image", "Please select or drag & drop an image first.")
            return

        prompt_text = self.prompt_entry.get().strip()
        mode = self.mode_var.get()

        # Update prompt display before sending
        self.update_prompt_display()

        if not prompt_text:
            if mode == "caption":
                prompt_text = (
                    "Generate an Instagram caption and hashtags for this photo. "
                    "Focus on cinematic mood and urban storytelling. Keep it concise and engaging."
                )
            elif mode == "evaluation":
                prompt_text = (
                    "Critique this image from a photographic perspective. "
                    "Focus on composition, mood, lighting, and storytelling."
                )

        selected_model = self.model_var.get()

        self.btn_generate.config(state='disabled')
        self.btn_copy.config(state='disabled')
        self.progress.config(text="Generating...")
        self.output_box.delete(1.0, tk.END)

        threading.Thread(
            target=self.call_ollama_api,
            args=(self.image_b64, prompt_text, selected_model),
            daemon=True
        ).start()

    def call_ollama_api(self, image_b64, prompt, model):
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64]
        }
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json=payload,
                stream=True,
                timeout=120
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self.append_text(f"\nRequest failed: {e}\n")
            self.after(0, lambda: self.progress.config(text=""))
            self.after(0, lambda: self.btn_generate.config(state='normal'))
            return

        full_response = ""
        known_fields = {f.name for f in fields(OllamaResponse)}

        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode())
                filtered_data = {k: v for k, v in data.items() if k in known_fields}
                resp = OllamaResponse(**filtered_data)
                self.append_text(resp.response)
                full_response += resp.response
                if resp.done:
                    break

        self.append_text("\n\n--- Done ---\n")
        self.after(0, lambda: self.progress.config(text="Done!"))
        self.after(0, lambda: self.btn_generate.config(state='normal'))
        self.after(0, lambda: self.btn_copy.config(state='normal'))

        # Auto-copy if pyperclip is installed
        if pyperclip:
            pyperclip.copy(full_response)
            self.append_text("[Output copied to clipboard]\n")
        else:
            self.append_text("[Install 'pyperclip' to enable automatic clipboard copying]\n")

        self.last_response = full_response

    def copy_to_clipboard(self):
        text = self.output_box.get(1.0, tk.END).strip()
        if not text:
            messagebox.showinfo("Nothing to copy", "No output to copy.")
            return
        if pyperclip:
            pyperclip.copy(text)
            messagebox.showinfo("Copied", "Output copied to clipboard.")
        else:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Output copied to clipboard (using Tkinter).")

    def append_text(self, text):
        def inner():
            self.output_box.insert(tk.END, text)
            self.output_box.see(tk.END)
        self.after(0, inner)

if __name__ == "__main__":
    app = OllamaApp()
    app.mainloop()
