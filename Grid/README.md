# 2x2 Image Grid Generator

This app lets you:

- choose a folder that contains images
- choose the folder where the PDF should be saved
- generate a PDF named `2x2.pdf` that places those images in a 2x2 grid
- automatically create extra pages when there are more than 4 images
- keep the last page partially filled when only 1 to 3 images remain

## How to run

1. Open PowerShell in this folder.
2. Run:

```powershell
python app.py
```

## Supported image types

`jpg`, `jpeg`, `png`, `bmp`, `gif`, `webp`, `tif`, `tiff`

## Output

The app generates a `.pdf` file directly.
