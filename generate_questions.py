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
    return """Generate a single USMLE-style pediatric question as a CSV row with the following format: record_id, question, anchor, answerchoice_a, answerchoice_b, answerchoice_c, answerchoice_d, answerchoice_e, correct_answer, answer_explanation, age, subject
    Instructions:
    - Return only a single row of comma-separated values (no headers, no newlines, no quotes).
    - The 'question' should be a full clinical vignette only.
    - The 'anchor' is the main clinical question being asked — e.g., "What is the most likely diagnosis?" or "What is the next best step in management?"
    - The five answer choices should be distinct and appropriate.
    - 'correct_answer' should be one of: a, b, c, d, or e.
    - 'answer_explanation' should include why the correct answer is correct and why the others are not.
    - 'age' should be in years as a decimal (e.g., 0.5 for 6 months).
    - 'subject' must be the number {subject_number} from the map below.

Subject number map:
1 = Adolescent Medicine
2 = Cardiology
3 = Dermatology
4 = Development
5 = Emergency/Critical Care
6 = Endocrinology
7 = Gastroenterology
8 = Genetic Disorders
9 = Hematology
10 = Immunizations
11 = Immunology/Allergy/Rheumatology
12 = Infectious Disease
13 = Metabolic
14 = Neurology
15 = Newborn Medicine
16 = Nutrition
17 = Oncology
18 = Ophthalmology
19 = Orthopaedics
20 = Nephrology/Urology
21 = Poisoning/Burns/Injury Prevention
22 = Pulmonology"""



def generate_question(subject_number):
    prompt = get_question_prompt(subject_number)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
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
