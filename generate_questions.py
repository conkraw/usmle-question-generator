import os
import openai
import pandas as pd
import random
import uuid
import smtplib
from datetime import date
from email.message import EmailMessage

openai.api_key = os.getenv("OPENAI_API_KEY")

SUBJECTS = list(range(1, 23))  # 1–22
TODAY = date.today().isoformat()
FILENAME = f"questions/questions_{TODAY}.csv"

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

def generate_record_id():
    return uuid.uuid4().hex[:6].upper()

def get_question_prompt(subject_number):
    return f"""Generate one USMLE-style pediatric question in the following CSV format:

record_id, question (vignette only), anchor (main clinical question), answerchoice_a, answerchoice_b, answerchoice_c, answerchoice_d, answerchoice_e, correct_answer, answer_explanation (detailed), age (in years), subject (use {subject_number})

Return only the values in a CSV row format, no headers or explanations."""

def generate_question(subject_number):
    prompt = get_question_prompt(subject_number)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    csv_line = response.choices[0].message['content'].strip()
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
