import base64
import json
import requests
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, scrolledtext
from dataclasses import dataclass, fields
from typing import Optional, List, Any
import io

try:
    import pyperclip
except ImportError:
    pyperclip = None

# Add these imports for CR3 support
try:
    import rawpy
    import imageio.v2 as imageio
except ImportError:
    rawpy = None
    imageio = None

# Add Pillow for image preview
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

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
        self.title("Ollama Photo Caption & Evaluation")
        self.geometry("700x600")

        self.image_path = None
        self.image_b64 = None
        self.preview_imgtk = None  # Prevent garbage collection

        # Add model selection variable
        self.model_var = tk.StringVar(value="llava")

        self.create_widgets()
        self.make_drag_and_drop_work()

    def create_widgets(self):
        # Frame for image select + drag-drop
        frm = ttk.Frame(self)
        frm.pack(padx=10, pady=10, fill='x')

        self.img_label = ttk.Label(frm, text="Drag & drop an image here or click 'Select Image'")
        self.img_label.pack(fill='x')

        btn_select = ttk.Button(frm, text="Select Image", command=self.select_image)
        btn_select.pack(pady=5)

        # Add image preview label
        self.preview_label = ttk.Label(frm)
        self.preview_label.pack(pady=5)

        # Model selector
        model_frame = ttk.Frame(self)
        model_frame.pack(padx=10, pady=5, fill='x')
        ttk.Label(model_frame, text="Choose model:").pack(side='left')
        model_options = ["gemma3", "llava"]
        model_menu = ttk.OptionMenu(model_frame, self.model_var, self.model_var.get(), *model_options)
        model_menu.pack(side='left', padx=10)

        # Option to choose caption or evaluation
        self.mode_var = tk.StringVar(value="caption")
        modes = [("Instagram Caption", "caption"), ("Photo Evaluation", "evaluation")]
        mode_frame = ttk.Frame(self)
        mode_frame.pack(padx=10, pady=5, fill='x')
        ttk.Label(mode_frame, text="Choose mode:").pack(side='left')
        for text, val in modes:
            ttk.Radiobutton(mode_frame, text=text, variable=self.mode_var, value=val).pack(side='left', padx=10)

        # Custom prompt input
        ttk.Label(self, text="Custom prompt (optional):").pack(anchor='w', padx=10)
        self.prompt_entry = ttk.Entry(self, width=80)
        self.prompt_entry.pack(padx=10, pady=5, fill='x')

        # Button to generate
        self.btn_generate = ttk.Button(self, text="Generate", command=self.on_generate)
        self.btn_generate.pack(pady=10)

        # Output text box (scrolled)
        self.output_box = scrolledtext.ScrolledText(self, height=15, wrap='word')
        self.output_box.pack(padx=10, pady=10, fill='both', expand=True)

    def make_drag_and_drop_work(self):
        # On Windows, simplest drag and drop support via window binding for dropped files
        # It gives you a string with file paths separated by space
        def drop(event):
            # Extract file path
            files = self.tk.splitlist(event.data)
            if files:
                filepath = files[0]
                if filepath.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".cr3")):
                    self.load_image(filepath)
                else:
                    messagebox.showerror("Invalid file", "Please drop a valid image file.")
            return "break"

        # Bind drop event (Windows only)
        self.img_label.drop_target_register = getattr(self.img_label, "drop_target_register", lambda *a: None)
        self.img_label.drop_target_register('DND_Files')
        self.img_label.dnd_bind = getattr(self.img_label, "dnd_bind", lambda *a: None)
        self.img_label.dnd_bind('<<Drop>>', drop)

        # For macOS/Linux you need additional libs, so we fallback to file picker

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
                    messagebox.showerror("Missing dependency", "rawpy and imageio are required for CR3 support.\nInstall with: pip install rawpy imageio")
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
            self.preview_label.config(text="Pillow not installed, preview unavailable.")
            return
        if img_bytes is None:
            self.preview_label.config(image='', text="No preview available.")
            self.preview_imgtk = None
            return
        try:
            img = Image.open(io.BytesIO(img_bytes))
            img.thumbnail((300, 300))
            self.preview_imgtk = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_imgtk, text='')
        except Exception as e:
            self.preview_label.config(text=f"Preview error: {e}")
            self.preview_imgtk = None

    def on_generate(self):
        if not self.image_b64:
            messagebox.showwarning("No image", "Please select or drag & drop an image first.")
            return

        prompt_text = self.prompt_entry.get().strip()
        mode = self.mode_var.get()

        # Set default prompt if none provided
        if not prompt_text:
            if mode == "caption":
                prompt_text = ("Generate an Instagram caption and hashtags for this photo. "
                               "Focus on cinematic mood and urban storytelling. Keep it concise and engaging.")
            elif mode == "evaluation":
                prompt_text = ("Critique this image from a photographic perspective. "
                               "Focus on composition, mood, lighting, and storytelling.")

        # Get selected model
        selected_model = self.model_var.get()

        # Disable button during generation
        self.btn_generate.config(state='disabled')
        self.output_box.delete(1.0, tk.END)

        # Run network call in a separate thread so UI doesn't freeze
        threading.Thread(target=self.call_ollama_api, args=(self.image_b64, prompt_text, selected_model), daemon=True).start()

    def call_ollama_api(self, image_b64, prompt, model):
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64]
        }
        try:
            response = requests.post("http://localhost:11434/api/generate", json=payload, stream=True)
            response.raise_for_status()
        except requests.RequestException as e:
            self.append_text(f"\nRequest failed: {e}")
            self.btn_generate.config(state='normal')
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

        # Copy to clipboard if pyperclip is installed
        if pyperclip:
            pyperclip.copy(full_response)
            self.append_text("[Response copied to clipboard]\n")
        else:
            self.append_text("[Install 'pyperclip' to enable clipboard copying]\n")

        self.btn_generate.config(state='normal')

    def append_text(self, text):
        def inner():
            self.output_box.insert(tk.END, text)
            self.output_box.see(tk.END)
        self.after(0, inner)

if __name__ == "__main__":
    app = OllamaApp()
    app.mainloop()
