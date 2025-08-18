with open("quiz-questions/1vs1200.txt", "r", encoding="koi8-r") as f:
    text = f.read()

parts = text.strip().split("\n\n")

for part in parts[:5]:
    lines = part.split("\n")
    if len(lines) >= 2:
        print("Вопрос:", lines[0])
        print("Ответ :", lines[1])
        print("-" * 30)
        