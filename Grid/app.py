from __future__ import annotations

import html
import math
import subprocess
import tempfile
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, Tk, filedialog, messagebox, ttk


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]


def find_images(folder: Path) -> list[Path]:
    return sorted(
        [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda path: path.name.lower(),
    )


def chunked(items: list[Path], size: int) -> list[list[Path]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_html(image_paths: list[Path], source_folder: Path) -> str:
    pages = chunked(image_paths, 4)
    page_markup: list[str] = []

    for page_images in pages:
        cards = []
        for image_path in page_images:
            cards.append(
                f"""
                <figure class="image-card">
                  <img src="{image_path.resolve().as_uri()}" alt="{html.escape(image_path.name)}">
                </figure>
                """.strip()
            )

        page_markup.append(
            f"""
            <section class="page">
              <div class="grid grid-{len(page_images)}">
                {' '.join(cards)}
              </div>
            </section>
            """.strip()
        )

    title = html.escape(f"2x2 Image Grid - {source_folder.name}")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    :root {{
      --page-width: 8.5in;
      --page-height: 11in;
      --page-padding: 0.4in;
      --page-gap: 0.18in;
      --page-bg: #ffffff;
      --surface: #f5f1eb;
      --border: #e6ddd2;
      --text: #2c241d;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      padding: 24px;
      background: linear-gradient(180deg, #efe7dd 0%, #f8f4ef 100%);
      color: var(--text);
      font-family: "Segoe UI", Tahoma, sans-serif;
    }}

    .document {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 24px;
    }}

    .page {{
      width: var(--page-width);
      min-height: var(--page-height);
      padding: var(--page-padding);
      background: var(--page-bg);
      box-shadow: 0 18px 50px rgba(70, 48, 22, 0.12);
      display: flex;
      page-break-after: always;
    }}

    .grid {{
      flex: 1;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: var(--page-gap);
      align-content: start;
    }}

    .image-card {{
      margin: 0;
      border: 1px solid var(--border);
      background: var(--surface);
      overflow: hidden;
      aspect-ratio: 1 / 1;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .image-card img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #fff;
      display: block;
    }}

    @page {{
      size: letter portrait;
      margin: 0.35in;
    }}

    @media print {{
      body {{
        padding: 0;
        background: #fff;
      }}

      .document {{
        gap: 0;
      }}

      .page {{
        box-shadow: none;
        width: auto;
        min-height: auto;
        padding: 0;
        break-after: page;
      }}
    }}

    @media (max-width: 900px) {{
      body {{
        padding: 12px;
      }}

      .page {{
        width: 100%;
        min-height: auto;
      }}
    }}
  </style>
</head>
<body>
  <main class="document">
    {' '.join(page_markup)}
  </main>
</body>
</html>
"""


def build_two_image_html(image_paths: list[Path], source_folder: Path, stacked: bool) -> str:
    pages = chunked(image_paths, 2)
    page_markup: list[str] = []

    for page_images in pages:
        cards = []
        for image_path in page_images:
            cards.append(
                f"""
                <figure class="image-card">
                  <img src="{image_path.resolve().as_uri()}" alt="{html.escape(image_path.name)}">
                </figure>
                """.strip()
            )

        page_markup.append(
            f"""
            <section class="page">
              <div class="grid {'stack' if stacked else 'side'}">
                {' '.join(cards)}
              </div>
            </section>
            """.strip()
        )

    title = html.escape(f"2-Image Page - {source_folder.name}")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      padding: 0;
    }}

    .page {{
      width: 210mm;
      height: 297mm;
      padding: 0.2in;
      display: flex;
      page-break-after: always;
    }}

    .grid {{
      flex: 1;
      display: grid;
      gap: 3px;
      min-width: 0;
      min-height: 0;
    }}

    .grid.side {{
      grid-template-columns: 1fr 1fr;
      grid-template-rows: 1fr;
    }}

    .grid.stack {{
      grid-template-columns: 1fr;
      grid-template-rows: 1fr 1fr;
    }}

    .image-card {{
      margin: 0;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .image-card img {{
      max-width: 100%;
      max-height: 100%;
      width: auto;
      height: auto;
      object-fit: contain;
      display: block;
    }}

    @page {{
      size: A4 portrait;
      margin: 0;
    }}
  </style>
</head>
<body>
  <main>
    {' '.join(page_markup)}
  </main>
</body>
</html>
"""


def find_browser() -> Path:
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate

    raise FileNotFoundError("Chrome or Edge is required to generate PDFs automatically.")


def _render_html_to_pdf(html_content: str, output_file: Path) -> None:
    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    browser_path = find_browser()
    with tempfile.TemporaryDirectory() as temp_dir:
        html_file = Path(temp_dir) / "image-grid.html"
        html_file.write_text(html_content, encoding="utf-8")

        command = [
            str(browser_path),
            "--headless=new",
            f"--print-to-pdf={output_file}",
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            html_file.resolve().as_uri(),
        ]

        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not output_file.exists():
            error_text = (result.stderr or result.stdout).strip()
            raise OSError(error_text or "The browser could not generate the PDF.")


def generate_document(source_folder: Path, output_file: Path) -> tuple[int, int]:
    images = find_images(source_folder)
    if not images:
        raise ValueError("No supported images were found in the selected folder.")

    _render_html_to_pdf(build_html(images, source_folder), output_file)
    return len(images), math.ceil(len(images) / 4)


def generate_two_image_document(source_folder: Path, output_file: Path, stacked: bool) -> tuple[int, int]:
    images = find_images(source_folder)
    if not images:
        raise ValueError("No supported images were found in the selected folder.")

    _render_html_to_pdf(build_two_image_html(images, source_folder, stacked), output_file)
    return len(images), math.ceil(len(images) / 2)


class ImageGridApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("2x2 Image Grid Generator")
        self.root.geometry("720x460")
        self.root.minsize(640, 420)

        self.source_var = StringVar()
        self.output_var = StringVar()
        self.orientation_var = StringVar(value="side")
        self.status_var = StringVar(value="Choose a folder with images to get started.")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=BOTH, expand=True)

        title = ttk.Label(frame, text="Create 2x2 image pages", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(
            frame,
            text="Pick an image folder and an output folder. The app will save the PDF there as 2x2.pdf.",
            wraplength=640,
        )
        subtitle.pack(anchor="w", pady=(6, 18))

        self._build_picker_row(frame, "Image folder", self.source_var, self.choose_source_folder)
        self._build_picker_row(frame, "Output folder", self.output_var, self.choose_output_folder)

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(18, 10))

        generate_button = ttk.Button(button_row, text="Generate PDF", command=self.handle_generate)
        generate_button.pack(side=LEFT)

        open_button = ttk.Button(button_row, text="Open PDF", command=self.open_output)
        open_button.pack(side=LEFT, padx=(10, 0))

        clear_button = ttk.Button(button_row, text="Clear", command=self.clear_form)
        clear_button.pack(side=RIGHT)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(4, 10))

        two_image_title = ttk.Label(frame, text="Create a 2-image page (A4)", font=("Segoe UI", 13, "bold"))
        two_image_title.pack(anchor="w")

        orientation_row = ttk.Frame(frame)
        orientation_row.pack(fill="x", pady=(8, 4))

        ttk.Label(orientation_row, text="Layout", width=14).pack(side=LEFT)
        ttk.Radiobutton(
            orientation_row, text="Side by side", variable=self.orientation_var, value="side"
        ).pack(side=LEFT, padx=(0, 12))
        ttk.Radiobutton(
            orientation_row, text="Up and down", variable=self.orientation_var, value="stack"
        ).pack(side=LEFT)

        two_image_button_row = ttk.Frame(frame)
        two_image_button_row.pack(fill="x", pady=(6, 0))

        two_image_generate_button = ttk.Button(
            two_image_button_row, text="Generate 2-Image PDF", command=self.handle_generate_two_image
        )
        two_image_generate_button.pack(side=LEFT)

        two_image_open_button = ttk.Button(
            two_image_button_row, text="Open PDF", command=self.open_two_image_output
        )
        two_image_open_button.pack(side=LEFT, padx=(10, 0))

        status_label = ttk.Label(
            frame,
            textvariable=self.status_var,
            relief="groove",
            padding=12,
            anchor="w",
            wraplength=640,
        )
        status_label.pack(fill="x", pady=(8, 0))

    def _build_picker_row(self, parent: ttk.Frame, label: str, variable: StringVar, command) -> None:
        container = ttk.Frame(parent)
        container.pack(fill="x", pady=8)

        ttk.Label(container, text=label, width=14).pack(side=LEFT)

        entry = ttk.Entry(container, textvariable=variable)
        entry.pack(side=LEFT, fill="x", expand=True, padx=(0, 10))

        ttk.Button(container, text="Browse", command=command).pack(side=RIGHT)

    def choose_source_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select the folder containing images")
        if not folder:
            return

        folder_path = Path(folder)
        self.source_var.set(str(folder_path))

        if not self.output_var.get().strip():
            self.output_var.set(str(folder_path))

        image_count = len(find_images(folder_path))
        self.status_var.set(f"Found {image_count} supported image(s) in the selected folder.")

    def choose_output_folder(self) -> None:
        initial_dir = self.output_var.get().strip() or str(Path.cwd())
        folder = filedialog.askdirectory(title="Choose where to save the PDF", initialdir=initial_dir)
        if folder:
            self.output_var.set(folder)

    def handle_generate(self) -> None:
        source_text = self.source_var.get().strip()
        output_text = self.output_var.get().strip()

        if not source_text:
            messagebox.showerror("Missing folder", "Please choose the folder that contains your images.")
            return

        if not output_text:
            messagebox.showerror("Missing output folder", "Please choose the folder where the PDF should be saved.")
            return

        source_folder = Path(source_text)
        output_folder = Path(output_text)

        if not source_folder.exists() or not source_folder.is_dir():
            messagebox.showerror("Invalid folder", "The selected image folder does not exist.")
            return

        if not output_folder.exists() or not output_folder.is_dir():
            messagebox.showerror("Invalid folder", "The selected output folder does not exist.")
            return

        output_file = output_folder / "2x2.pdf"

        try:
            image_count, page_count = generate_document(source_folder, output_file)
        except ValueError as error:
            messagebox.showerror("No images found", str(error))
            self.status_var.set(str(error))
            return
        except OSError as error:
            messagebox.showerror("Save failed", f"Could not save the PDF.\n\n{error}")
            self.status_var.set("The PDF could not be saved.")
            return

        self.status_var.set(
            f"Created 2x2.pdf in the selected folder with {image_count} image(s) across {page_count} page(s)."
        )
        messagebox.showinfo(
            "PDF created",
            f"Created:\n{output_file}\n\nImages: {image_count}\nPages: {page_count}",
        )

    def handle_generate_two_image(self) -> None:
        source_text = self.source_var.get().strip()
        output_text = self.output_var.get().strip()

        if not source_text:
            messagebox.showerror("Missing folder", "Please choose the folder that contains your images.")
            return

        if not output_text:
            messagebox.showerror("Missing output folder", "Please choose the folder where the PDF should be saved.")
            return

        source_folder = Path(source_text)
        output_folder = Path(output_text)

        if not source_folder.exists() or not source_folder.is_dir():
            messagebox.showerror("Invalid folder", "The selected image folder does not exist.")
            return

        if not output_folder.exists() or not output_folder.is_dir():
            messagebox.showerror("Invalid folder", "The selected output folder does not exist.")
            return

        output_file = output_folder / "2image.pdf"
        stacked = self.orientation_var.get() == "stack"

        try:
            image_count, page_count = generate_two_image_document(source_folder, output_file, stacked)
        except ValueError as error:
            messagebox.showerror("No images found", str(error))
            self.status_var.set(str(error))
            return
        except OSError as error:
            messagebox.showerror("Save failed", f"Could not save the PDF.\n\n{error}")
            self.status_var.set("The PDF could not be saved.")
            return

        self.status_var.set(
            f"Created 2image.pdf in the selected folder with {image_count} image(s) across {page_count} page(s)."
        )
        messagebox.showinfo(
            "PDF created",
            f"Created:\n{output_file}\n\nImages: {image_count}\nPages: {page_count}",
        )

    def open_two_image_output(self) -> None:
        output_text = self.output_var.get().strip()
        if not output_text:
            messagebox.showerror("Missing output folder", "There is no output folder selected yet.")
            return

        output_path = Path(output_text) / "2image.pdf"
        if not output_path.exists():
            messagebox.showerror("File not found", "Generate the PDF first, then you can open it.")
            return

        webbrowser.open(output_path.resolve().as_uri())

    def open_output(self) -> None:
        output_text = self.output_var.get().strip()
        if not output_text:
            messagebox.showerror("Missing output folder", "There is no output folder selected yet.")
            return

        output_path = Path(output_text) / "2x2.pdf"
        if not output_path.exists():
            messagebox.showerror("File not found", "Generate the PDF first, then you can open it.")
            return

        webbrowser.open(output_path.resolve().as_uri())

    def clear_form(self) -> None:
        self.source_var.set("")
        self.output_var.set("")
        self.status_var.set("Choose a folder with images to get started.")


def main() -> None:
    root = Tk()
    ttk.Style().theme_use("vista")
    ImageGridApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
