"""Technical document (Markdown) -> PDF for the submission form.

    make pdf        # -> submissions/<team>.pdf

Not part of the pipeline: it only prints docs/technical_document.md. Markdown is rendered with
markdown-it-py (CommonMark + tables, the same rules GitHub uses) and printed by headless Chrome.
Without Chrome it leaves the HTML next to the target; open that and print to PDF by hand.
"""

import os
import shutil
import subprocess
import sys

from markdown_it import MarkdownIt

CSS = """
@page { size: A4; margin: 18mm 17mm; }
* { box-sizing: border-box; }
body { font: 10.3pt/1.42 -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif;
       color: #111; margin: 0; }
h1 { font-size: 19pt; margin: 0 0 6pt; }
h2 { font-size: 13.5pt; margin: 16pt 0 5pt; border-bottom: 0.6pt solid #999;
     padding-bottom: 2pt; break-after: avoid; }
p { margin: 5pt 0; orphans: 3; widows: 3; }
ul, ol { margin: 4pt 0; padding-left: 16pt; }
li { margin: 2pt 0; }
li > p { margin: 2pt 0; }
code { font: 8.9pt Menlo, Consolas, monospace; background: #f2f2f2; padding: 0 2pt;
       border-radius: 2pt; overflow-wrap: anywhere; }
pre { background: #f5f5f5; border: 0.5pt solid #ccc; padding: 6pt 8pt; margin: 6pt 0;
      break-inside: avoid; white-space: pre-wrap; }
pre code { background: none; padding: 0; font-size: 8.2pt; line-height: 1.3; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 9.2pt; }
th, td { border: 0.5pt solid #999; padding: 2.5pt 5pt; text-align: left; vertical-align: top; }
th { background: #eee; }
tr { break-inside: avoid; }
"""

CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


def main():
    src, out = sys.argv[1], os.path.abspath(sys.argv[2])
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    title = text.splitlines()[0].lstrip("# ").replace("&", "&amp;")
    body = MarkdownIt("commonmark").enable("table").render(text)
    html = out[:-4] + ".html"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(html, "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{}</title>"
                 "<style>{}</style></head><body>{}</body></html>".format(title, CSS, body))
    chrome = next((c for c in CHROME if os.path.exists(c) or shutil.which(c)), None)
    if not chrome:
        sys.exit("Chrome not found. Open {} in a browser and print it to PDF.".format(html))
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--print-to-pdf=" + out, "file://" + html],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(html)
    print("wrote", out)


if __name__ == "__main__":
    main()
