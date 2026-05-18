from fasthtml.common import *
import markdown
import json

app, rt = fast_app(hdrs=(
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css"),
    Style("""
        .slide { display: none; height: 100vh; padding: 2rem; }
        .slide.active { display: block; }
        .controls { position: fixed; bottom: 20px; right: 20px; }
        pre code { white-space: pre-wrap; font-size: 0.8rem; }
        ul { margin-bottom: 1rem; }
    """),
    Script("""
        let currentSlide = 0;
        function showSlide(n) {
            let slides = document.getElementsByClassName("slide");
            for (let i = 0; i < slides.length; i++) {
                slides[i].classList.remove("active");
            }
            if (n >= slides.length) { currentSlide = slides.length - 1; }
            if (n < 0) { currentSlide = 0; }
            slides[currentSlide].classList.add("active");
        }
        function nextSlide() { currentSlide++; showSlide(currentSlide); }
        function prevSlide() { currentSlide--; showSlide(currentSlide); }
        document.addEventListener("keydown", function(e) {
            if (e.key === "ArrowRight") nextSlide();
            if (e.key === "ArrowLeft") prevSlide();
        });
        window.onload = () => showSlide(0);
    """)
))

def read_file(path):
    try:
        with open(path, 'r') as f: return f.read()
    except: return ""

def md2html(text):
    return markdown.markdown(text, extensions=['tables', 'fenced_code'])

@rt("/")
def get():
    with open("prioritized_todos.json", "r") as f:
        todos = json.load(f)
    sometime_todos = [t for t in todos if t["priority"] == "sometime"]

    with open("deviations.txt", "r") as f:
        deviations = f.read()

    with open("plan_status_summary.txt", "r") as f:
        plan_status = f.read()

    with open("action_items.md", "r") as f:
        action_items = f.read()

    return Titled("MechDSL Status Report",
        Container(
            Div(
                H1("MechDSL Status Report"),
                P("Press Left/Right arrows to navigate slides."),
                cls="slide active"
            ),

            Div(
                H2("1. Adherence to Design Docs"),
                Div(NotStr(md2html("```text\n" + deviations + "\n```"))),
                cls="slide"
            ),

            Div(
                H2("2. Plans Status"),
                Div(NotStr(md2html("```text\n" + plan_status + "\n```"))),
                cls="slide"
            ),

            Div(
                H2("3. Technical Debts (TODOs)"),
                H3("Urgent / Before Release"),
                P("None found."),
                H3("Sometime"),
                P(f"Total 'sometime' TODOs found: {len(sometime_todos)}. Showing first 5 for brevity:"),
                Ul(*[Li(f"{t['file']}:{t['line']} - {t['text']}") for t in sometime_todos[:5]]),
                cls="slide"
            ),

            Div(
                H2("4. Suggested Action Items & Execution Order"),
                Div(NotStr(md2html(action_items))),
                cls="slide"
            ),

            Div(
                Button("Prev", onclick="prevSlide()", cls="secondary"),
                Span(" "),
                Button("Next", onclick="nextSlide()"),
                cls="controls"
            )
        )
    )

serve()
