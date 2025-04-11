import os
import openai
import pandas as pd
import random
import json
from datetime import date
import re
import hashlib
import smtplib
from email.message import EmailMessage

# Set your OpenAI key and email credentials using GitHub secrets or env vars
openai.api_key = os.getenv("OPENAI_API_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# File constants
INPUT_CSV = "STUDENTASSESSMENTCRE-MXREPORTBATCHWORK_DATA_2025-04-11_1422.csv"
OUTPUT_CSV = "all_questions.csv"
PROCESSED_CSV = "processed.csv"

SUBJECT_MAP = { ... }  # same as before
NBME_CATEGORY_MAP = { ... }  # same as before

def extract_info(text):
    age_match = re.search(r'(\d{1,2})[-\s]?(year[-\s]?old)', text, re.IGNORECASE)
    return float(age_match.group(1)) if age_match else 14.0

def classify_question_metadata(original_question):
    ...  # same as before

def get_prompt(original_question, age, anchor, topic):
    ...  # same as before

def generate_question(prompt):
    ...  # same as before

def send_email(filepath, body_text):
    ...  # same as before

def main():
    df = pd.read_csv(INPUT_CSV)
    if os.path.exists(PROCESSED_CSV):
        processed = pd.read_csv(PROCESSED_CSV)
        processed_ids = set(processed["record_id"])
        processed_hashes = set(processed["question_hash"]) if "question_hash" in processed.columns else set()
    else:
        processed_ids = set()
        processed_hashes = set()

    df["question_hash"] = df["question"].apply(lambda q: hashlib.sha256(q.encode()).hexdigest())
    unprocessed_df = df[(~df["record_id"].isin(processed_ids)) & (~df["question_hash"].isin(processed_hashes))]

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

    processed_entry = pd.DataFrame([{
        "record_id": original_id,
        "question_hash": hashlib.sha256(original_question.encode()).hexdigest()
    }])
    processed_entry.to_csv(PROCESSED_CSV, mode='a', header=not os.path.exists(PROCESSED_CSV), index=False)

    summary = f"Today's NBME-style Pediatric Question:\n\nAnchor: {anchor}\nTopic: {topic}\n\n{question_data['question']}\n\nAnswer Explanation:\n{question_data['answer_explanation']}"
    send_email(OUTPUT_CSV, summary)

if __name__ == "__main__":
    main()
