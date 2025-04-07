import os
from openai import OpenAI
import pandas as pd
import random
import uuid
import smtplib
from datetime import date
from email.message import EmailMessage

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SUBJECTS = list(range(1, 23))  # 1–22
TODAY = date.today().isoformat()
FILENAME = f"questions/questions_{TODAY}.csv"

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

def generate_record_id():
    return uuid.uuid4().hex[:6].upper()

def get_question_prompt(subject_number):
    return f"""Generate a single USMLE-style pediatric question as a CSV row with the following format, with exactly 12 comma-separated values and no extra characters:

record_id,question,anchor,answerchoice_a,answerchoice_b,answerchoice_c,answerchoice_d,answerchoice_e,correct_answer,answer_explanation,age,subject

Rules:
1. Output exactly one line with exactly 12 fields separated by commas, with no header and no additional text.
2. Do not include any quotation marks (") or any extra punctuation other than commas; if a comma is needed within a field, replace it with a semicolon.
3. The 'record_id' should be a random string with no quotes.
4. The 'question' should be a realistic pediatric clinical vignette.
5. The 'anchor' is a concise clinical question (e.g., What is the most likely diagnosis?).
6. Provide exactly five answer choices (answerchoice_a to answerchoice_e) that are distinct and brief.
7. The 'correct_answer' must be one of: a, b, c, d, or e in lowercase.
8. The 'answer_explanation' should briefly explain why the correct answer is right and why the others are not.
9. The 'age' should be a decimal number representing the patient's age in years (for example, 0.5 for 6 months).
10. The 'subject' must be exactly the number {subject_number} (without quotes).

For example (this is only for reference and should not be output):
NKX5W27B,A 4-year-old boy presents with a white reflex on exam,What is the most likely diagnosis?,Cataract,Retinoblastoma,Strabismus,Glaucoma,Persistent fetal vasculature,b,Retinoblastoma should be suspected in any child with leukocoria; other options are less consistent,4,18

Return only the CSV row, nothing else."""



def generate_question(subject_number):
    prompt = get_question_prompt(subject_number)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    csv_line = response.choices[0].message.content.strip()
    return csv_line

def send_email(filepath):
    msg = EmailMessage()
    msg["Subject"] = f"🩺 Daily USMLE Questions - {TODAY}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    msg.set_content("Attached are today's 5 USMLE-style pediatric questions.")

    with open(filepath, "rb") as f:
        file_data = f.read()
        msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=os.path.basename(filepath))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

def main():
    os.makedirs("questions", exist_ok=True)
    rows = []

    for _ in range(5):
        subject = random.choice(SUBJECTS)
        row_text = generate_question(subject)
        parts = row_text.split(",")
        if len(parts) >= 12:
            rows.append(parts[:12])  # Handle slight over-returning

    df = pd.DataFrame(rows, columns=[
        "record_id", "question", "anchor", "answerchoice_a", "answerchoice_b",
        "answerchoice_c", "answerchoice_d", "answerchoice_e", "correct_answer",
        "answer_explanation", "age", "subject"
    ])
    df.to_csv(FILENAME, index=False)

    send_email(FILENAME)

if __name__ == "__main__":
    main()
