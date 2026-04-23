pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --icon app.ico `
  --add-data "app.ico;." `
  --exclude-module numpy `
  --name ImageCompareTool `
  image_compare_tool.py
