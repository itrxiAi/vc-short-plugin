import sys

# Windows 控制台默认 cp1252 编码，打印中文会崩，强制 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from vcshort.cli import main

if __name__ == "__main__":
    sys.exit(main())
