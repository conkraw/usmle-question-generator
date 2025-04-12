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
INPUT_CSV = "file.csv"
OUTPUT_CSV = "all_questions.csv"
PROCESSED_CSV = "processed.csv"

SUBJECT_MAP = { ... }  # same as before
NBME_CATEGORY_MAP = { ... }  # same as before

def extract_info(text):
    age_match = re.search(r'(\d{1,2})[-\s]?(year[-\s]?old)', text, re.IGNORECASE)
    return float(age_match.group(1)) if age_match else 14.0

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
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": metadata_prompt}],
            temperature=0.2,
            max_tokens=300,
        )
        content = response.choices[0].message['content']
        meta = json.loads(content)
        return (
            meta.get("topic", "pending"),
            int(meta.get("subject", 23)),
            int(meta.get("nbme_cat", 17)),
            meta.get("anchor", "What is the most likely diagnosis?")
        )
    except Exception as e:
        print(f"Metadata classification failed: {e}")
        return None

def get_prompt(original_question, age, anchor, topic):
    return f"""
You are a board-certified pediatrician writing a USMLE-style NBME shelf question. Use the following specifications:

- Keep the clinical concept focused on: {topic}
- Change the scenario, setting, and patient context (but preserve the core diagnosis or management decision)
- Keep the age close to {age} years (±2 years)
- Write a detailed clinical vignette (at least 10 sentences) including:
  - Relevant history, review of systems, medications, past medical history
  - Vitals, physical exam findings, and labs (if applicable)
  - Subtle or high-yield clues that help distinguish between close diagnoses

**Answer choices:**
- Create 5 realistic answer choices labeled a–e
- Use a mix of diagnostic terms, management steps, or treatments as appropriate to the anchor
- Include one correct answer and four strong distractors that are plausible but incorrect

**Answer explanation:**
- Start by clearly explaining why the correct answer is correct
- Then explain why each incorrect answer (b–e) is not the best choice
- Use step-by-step clinical reasoning and avoid vague or generic statements

Match this exact anchor for the question: {anchor}

Return ONLY a valid JSON object with these keys:
- record_id
- question
- anchor
- answerchoice_a
- answerchoice_b
- answerchoice_c
- answerchoice_d
- answerchoice_e
- correct_answer (must be one of "a", "b", "c", "d", or "e", lowercase)
- answer_explanation (robust, clear, 5+ sentences)
- age (in decimal years)
- subject (numeric ID)
- topic
- nbme_cat (numeric ID)
- type (question type code)

Original question: {original_question}
"""


def generate_question(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        output = response.choices[0].message['content'].strip()

        # Extract JSON safely
        first_brace = output.find('{')
        last_brace = output.rfind('}')
        if first_brace != -1 and last_brace != -1:
            output = output[first_brace:last_brace+1]

        data = json.loads(output)

        # Normalize correct_answer to a single lowercase letter
        correct = str(data.get("correct_answer", "")).strip().lower()
        if correct not in ["a", "b", "c", "d", "e"]:
            raise ValueError(f"Invalid correct_answer format: {correct}")
        data["correct_answer"] = correct

        return data

    except Exception as e:
        print(f"Question generation failed: {e}")
        return None


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
    result = classify_question_metadata(original_question)
    if result is None:
        print("Skipping row due to failed metadata classification.")
        return
    topic, subject, nbme_cat, anchor = result
    qtype = 1 if "diagnosis" in anchor.lower() else (4 if "management" in anchor.lower() else 3)

    prompt = get_prompt(original_question, age, anchor, topic)

    try:
        question_data = generate_question(prompt)
        if question_data is None:
            print("Skipping row due to failed question generation.")
            return
    except Exception as e:
        print(f"Failed to generate question: {e}")
        return
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
    
    summary = f"Today's NBME-style Pediatric Question:
    Record ID: {question_data['record_id']}
    Anchor: {anchor}
    Topic: {topic}
    {question_data['question']}
    Answer Choices:
    A. {question_data['answerchoice_a']}
    B. {question_data['answerchoice_b']}
    C. {question_data['answerchoice_c']}
    D. {question_data['answerchoice_d']}
    E. {question_data['answerchoice_e']}
    
    Correct Answer: {question_data['correct_answer'].upper()}
    
    Answer Explanation:
    {question_data['answer_explanation']}"

    send_email(OUTPUT_CSV, summary)

if __name__ == "__main__":
    main()


