"""Script to generate a presentation from PITCH_DECK.md."""
import os
import sys
import re

# Set UTF-8 encoding for Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PITCH_MD_PATH = os.path.join(PROJECT_ROOT, "PITCH_DECK.md")
OUTPUT_HTML_PATH = os.path.join(PROJECT_ROOT, "pitch_deck.html")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TRACE — Cross-Bank Mule Account Detection Network</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #090D16;
            --card-bg: #131A29;
            --accent-blue: #3B82F6;
            --accent-cyan: #06B6D4;
            --accent-emerald: #10B981;
            --accent-rose: #F43F5E;
            --text-primary: #F8FAFC;
            --text-muted: #94A3B8;
            --border-color: #1E293B;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        header {
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            background: rgba(19, 26, 41, 0.7);
            backdrop-filter: blur(8px);
        }

        .logo {
            font-size: 20px;
            font-weight: 800;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .slide-counter {
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            color: var(--accent-cyan);
            background: rgba(6, 182, 212, 0.1);
            padding: 4px 12px;
            border-radius: 9999px;
            border: 1px solid rgba(6, 182, 212, 0.2);
        }

        .slide-container {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 40px;
            position: relative;
        }

        .slide {
            display: none;
            max-width: 1000px;
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 48px 56px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .slide.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(12px) scale(0.99); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        h1 {
            font-size: 38px;
            font-weight: 800;
            line-height: 1.2;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #FFFFFF, #94A3B8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        h2 {
            font-size: 24px;
            color: var(--accent-cyan);
            margin-bottom: 24px;
            font-weight: 600;
        }

        p, li {
            font-size: 17px;
            line-height: 1.6;
            color: #CBD5E1;
            margin-bottom: 12px;
        }

        ul {
            list-style: none;
            padding-left: 0;
            margin-top: 16px;
        }

        li {
            position: relative;
            padding-left: 28px;
            margin-bottom: 14px;
        }

        li::before {
            content: "⚡";
            position: absolute;
            left: 0;
            top: 1px;
            font-size: 14px;
            color: var(--accent-cyan);
        }

        blockquote {
            background: rgba(59, 130, 246, 0.08);
            border-left: 4px solid var(--accent-blue);
            padding: 14px 20px;
            border-radius: 8px;
            margin: 20px 0;
            font-style: italic;
            color: #E2E8F0;
        }

        .controls {
            padding: 20px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid var(--border-color);
            background: rgba(19, 26, 41, 0.7);
        }

        .nav-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 10px 24px;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
        }

        .nav-btn:hover:not(:disabled) {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
        }

        .nav-btn:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <span>🛡️</span> TRACE // Federated Mule Network
        </div>
        <div class="slide-counter" id="counter">Slide 1 of 8</div>
    </header>

    <main class="slide-container">
        <!-- SLIDES_INJECTED_HERE -->
    </main>

    <footer class="controls">
        <button class="nav-btn" id="prevBtn" onclick="prevSlide()">◀ Previous</button>
        <span style="color: var(--text-muted); font-size: 13px;">Use Left/Right arrow keys to navigate</span>
        <button class="nav-btn" id="nextBtn" onclick="nextSlide()">Next ▶</button>
    </footer>

    <script>
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');
        const counter = document.getElementById('counter');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');

        function updateSlide() {
            slides.forEach((s, idx) => {
                s.classList.toggle('active', idx === currentSlide);
            });
            counter.textContent = `Slide ${currentSlide + 1} of ${slides.length}`;
            prevBtn.disabled = currentSlide === 0;
            nextBtn.disabled = currentSlide === slides.length - 1;
        }

        function nextSlide() {
            if (currentSlide < slides.length - 1) {
                currentSlide++;
                updateSlide();
            }
        }

        function prevSlide() {
            if (currentSlide > 0) {
                currentSlide--;
                updateSlide();
            }
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight' || e.key === 'Space') nextSlide();
            if (e.key === 'ArrowLeft') prevSlide();
        });

        updateSlide();
    </script>
</body>
</html>
"""


def parse_markdown_to_slides(md_content: str) -> str:
    """Parses markdown slides demarcated by '---' into HTML slide blocks."""
    raw_slides = re.split(r'\n---\n', md_content)
    slide_html_list = []

    for i, slide_text in enumerate(raw_slides):
        slide_text = slide_text.strip()
        if not slide_text:
            continue

        # Extract title
        lines = slide_text.split('\n')
        body_lines = []
        h1 = ""
        h2 = ""

        for line in lines:
            if line.startswith('# '):
                h1 = line[2:].strip()
            elif line.startswith('## '):
                h2 = line[3:].strip()
            elif line.startswith('### '):
                if not h2:
                    h2 = line[4:].strip()
                else:
                    body_lines.append(f"<h3>{line[4:].strip()}</h3>")
            elif line.startswith('> '):
                body_lines.append(f"<blockquote>{line[2:].strip()}</blockquote>")
            elif line.startswith('- '):
                body_lines.append(f"<li>{line[2:].strip()}</li>")
            elif line.strip():
                body_lines.append(f"<p>{line.strip()}</p>")

        content_html = ""
        if h1:
            content_html += f"<h1>{h1}</h1>"
        if h2:
            content_html += f"<h2>{h2}</h2>"

        # Group list items in <ul>
        in_list = False
        formatted_body = []
        for bl in body_lines:
            if bl.startswith("<li>"):
                if not in_list:
                    formatted_body.append("<ul>")
                    in_list = True
                formatted_body.append(bl)
            else:
                if in_list:
                    formatted_body.append("</ul>")
                    in_list = False
                formatted_body.append(bl)
        if in_list:
            formatted_body.append("</ul>")

        content_html += "\n".join(formatted_body)
        slide_html_list.append(f'<div class="slide{" active" if i == 0 else ""}">{content_html}</div>')

    return "\n".join(slide_html_list)


def main():
    if not os.path.exists(PITCH_MD_PATH):
        print(f"Error: {PITCH_MD_PATH} not found.")
        sys.exit(1)

    with open(PITCH_MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    slides_html = parse_markdown_to_slides(md_text)
    full_html = HTML_TEMPLATE.replace("<!-- SLIDES_INJECTED_HERE -->", slides_html)

    with open(OUTPUT_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"✅ Generated pitch deck HTML: {OUTPUT_HTML_PATH}")


if __name__ == "__main__":
    main()
