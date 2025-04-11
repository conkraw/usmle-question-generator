import os
import openai
import pandas as pd
import random
import json
from datetime import date
import re
import smtplib
from email.message import EmailMessage

# Set your OpenAI key and email credentials using GitHub secrets or env vars
openai.api_key = os.getenv("OPENAI_API_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# File constants
INPUT_CSV = "file.csv"
OUTPUT_CSV = "all_questions.csv"
PROCESSED_CSV = "processed.csv"

SUBJECT_MAP = {
    1: "Adolescent Medicine", 2: "Cardiology", 3: "Dermatology", 4: "Development", 5: "Emergency/Critical Care",
    6: "Endocrinology", 7: "Gastroenterology", 8: "Genetic Disorders", 9: "Hematology", 10: "Immunizations",
    11: "Immunology/Allergy/Rheumatology", 12: "Infectious Disease", 13: "Metabolic", 14: "Neurology",
    15: "Newborn Medicine", 16: "Nutrition", 17: "Oncology", 18: "Ophthalmology", 19: "Orthopaedics",
    20: "Nephrology/Urology", 21: "Poisoning/Burns/Injury Prevention", 22: "Pulmonology", 23: "Pending"
}

NBME_CATEGORY_MAP = {
    1: "Behavioral health", 2: "Blood and lymphoreticular system", 3: "Cardiovascular system", 4: "Endocrine system",
    5: "Female reproductive and breast", 6: "Gastrointestinal system", 7: "General Principles", 8: "Immune System",
    9: "Male reproductive", 10: "Multisystem processes and disorders", 11: "Musculoskeletal system",
    12: "Nervous system and special senses", 13: "Pregnancy, childbirth, and the puerperium",
    14: "Renal and urinary system", 15: "Respiratory system", 16: "Skin and subcutaneous tissue",
    17: "Social Sciences"
}

def extract_info(text):
    age_match = re.search(r'(\d{1,2})[-\s]?(year[-\s]?old)', text, re.IGNORECASE)
    age = float(age_match.group(1)) if age_match else 14.0
    return age

def classify_question_metadata(original_question):
    metadata_prompt = f"""
You are an NBME question classifier. Given the following question text, return the best guesses for:

- topic (free text)
- subject (number from 1 to 22 based on pediatric subspecialties)
- nbme_cat (number from 1 to 17 based on USMLE content categories)
- anchor (question type such as: What is the most likely diagnosis?, What is the next best step in management?, etc.)

Respond only with a valid JSON object with these keys.

Example format:
{{ "topic": "gynecomastia", "subject": 1, "nbme_cat": 1, "anchor": "What is the most likely diagnosis?" }}

Question: {original_question}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": metadata_prompt}],
        temperature=0.2,
        max_tokens=300,
    )
    content = response.choices[0].message['content']
    try:
        meta = json.loads(content)
        return (
            meta.get("topic", "pending"),
            int(meta.get("subject", 23)),
            int(meta.get("nbme_cat", 17)),
            meta.get("anchor", "What is the most likely diagnosis?")
        )
    except Exception:
        return "pending", 23, 17, "What is the most likely diagnosis?"

def get_prompt(original_question, age, anchor, topic):
    return f"""
Rewrite this question into a new USMLE-style pediatric question. Keep the core concept ({topic}), but:
- Change the scenario, setting, and clinical details
- Keep the age close (e.g., ±2 years)
- Include at least 5 sentences in the vignette
- Generate 5 realistic answer choices
- Include a correct answer and 4 strong distractors
- Write a robust answer explanation (5+ sentences)
- Match the anchor: {anchor}

Return a JSON with these keys:
- record_id
- question
- anchor
- answerchoice_a to answerchoice_e
- correct_answer
- answer_explanation
- age
- subject (numeric ID)
- topic
- nbme_cat (numeric ID)
- type (question type code)

Original question: {original_question}
"""

def generate_question(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000
    )
    output = response.choices[0].message['content'].strip()
    try:
        question_json = json.loads(output)
    except json.JSONDecodeError:
        first_brace = output.find('{')
        last_brace = output.rfind('}')
        if first_brace != -1 and last_brace != -1:
            output = output[first_brace:last_brace+1]
            question_json = json.loads(output)
        else:
            raise ValueError("Failed to parse GPT output.")
    return question_json

def send_email(filepath, body_text):
    msg = EmailMessage()
    msg['Subject'] = f"\U0001FA7A Daily USMLE Pediatric Question - {date.today()}"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_RECIPIENT
    msg.set_content(body_text)
    with open(filepath, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="octet-stream", filename=os.path.basename(filepath))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

def main():
    df = pd.read_csv(INPUT_CSV)
    if os.path.exists(PROCESSED_CSV):
        processed = pd.read_csv(PROCESSED_CSV)
        processed_ids = set(processed["record_id"])
    else:
        processed_ids = set()

    unprocessed_df = df[~df["record_id"].isin(processed_ids)]
    if unprocessed_df.empty:
        send_email(OUTPUT_CSV, "✅ All questions have been processed.")
        return

    row = unprocessed_df.iloc[0]
    original_question = row["question"]
    original_id = row["record_id"]

    age = extract_info(original_question)
    topic, subject, nbme_cat, anchor = classify_question_metadata(original_question)
    qtype = 1 if "diagnosis" in anchor.lower() else (4 if "management" in anchor.lower() else 3)

    prompt = get_prompt(original_question, age, anchor, topic)

    try:
        question_data = generate_question(prompt)
    except Exception as e:
        print(f"Failed to generate question: {e}")
        return

    question_data["record_id"] = original_id
    question_data["subject"] = subject
    question_data["topic"] = topic
    question_data["nbme_cat"] = nbme_cat
    question_data["type"] = qtype

    cols = [
        "record_id", "question", "anchor",
        "answerchoice_a", "answerchoice_b", "answerchoice_c", "answerchoice_d", "answerchoice_e",
        "correct_answer", "answer_explanation", "age", "subject", "topic", "nbme_cat", "type"
    ]
    output_df = pd.DataFrame([question_data], columns=cols)

    if os.path.exists(OUTPUT_CSV):
        existing = pd.read_csv(OUTPUT_CSV)
        updated = pd.concat([existing, output_df], ignore_index=True)
        updated.to_csv(OUTPUT_CSV, index=False)
    else:
        output_df.to_csv(OUTPUT_CSV, index=False)

    pd.DataFrame([{"record_id": original_id}]).to_csv(PROCESSED_CSV, mode='a', header=not os.path.exists(PROCESSED_CSV), index=False)

    summary = f"Today's NBME-style Pediatric Question:\n\nAnchor: {anchor}\nTopic: {topic}\n\n{question_data['question']}\n\nAnswer Explanation:\n{question_data['answer_explanation']}"
    send_email(OUTPUT_CSV, summary)

if __name__ == "__main__":
    main()
