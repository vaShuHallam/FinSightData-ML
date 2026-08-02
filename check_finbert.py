"""
FinBERT quick verification — run this as a normal Python script in PyCharm
(or any terminal) to confirm FinBERT loads and classifies correctly before
trusting it in the real pipeline (app/sentiment/finbert_analyzer.py).

Setup (run once in PyCharm's terminal, inside your project's venv):
    pip install transformers torch

Then just run this file normally (right-click -> Run, or `python
check_finbert.py` in the terminal). Takes about a minute the first time
(downloads ~440MB of model weights; cached after that).

Expected output: the two obviously-positive headlines should come back
"positive" with high confidence, the negative one "negative", and the
neutral one "neutral" or close to it.
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_NAME = "ProsusAI/finbert"

print(f"Loading {MODEL_NAME} ...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
model.eval()
print(f"Loaded. Running on: {device}")
print(f"Label mapping: {model.config.id2label}\n")

test_headlines = [
    "Apple beats quarterly earnings expectations on strong iPhone demand",
    "Tesla shares slide after production miss and price cut announcement",
    "Company reports quarterly results in line with analyst expectations",
    "Microsoft unveils new AI features, stock hits record high",
]

inputs = tokenizer(
    test_headlines, padding=True, truncation=True, max_length=512, return_tensors="pt"
).to(device)

with torch.no_grad():
    logits = model(**inputs).logits
    probs = torch.nn.functional.softmax(logits, dim=-1).cpu().tolist()

id2label = {int(k): v for k, v in model.config.id2label.items()}

for headline, prob_row in zip(test_headlines, probs):
    scores = {id2label[i]: round(p, 3) for i, p in enumerate(prob_row)}
    top_label = max(scores, key=scores.get)
    print(f"[{top_label:<8} conf={scores[top_label]:.3f}]  {headline}")
    print(f"           full scores: {scores}\n")
