import os
import openai
import pandas as pd
import random
import uuid
import json
from datetime import date
import smtplib
from email.message import EmailMessage

# Set your OpenAI API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# Define the 22 subject numbers
SUBJECTS = list(range(1, 23))  # 1 to 22
TODAY = date.today().isoformat()
FILENAME = "all_questions.csv"  # Updated file name

def generate_record_id():
    return uuid.uuid4().hex[:8].upper()

def get_question_prompt(subject_number, anchor, setting):
    return f"""Generate a single USMLE-style pediatric question as a JSON object with the following keys:
- record_id: a random string (this value will be overwritten by the script)
- question: a detailed and lengthy clinical vignette describing a realistic pediatric scenario set in a {setting}. The vignette must be at least 5 sentences long.
- anchor: use the following clinical question exactly: {anchor}
- answerchoice_a: a brief answer option.
- answerchoice_b: a brief answer option.
- answerchoice_c: a brief answer option.
- answerchoice_d: a brief answer option.
- answerchoice_e: a brief answer option.
- correct_answer: one of "a", "b", "c", "d", or "e" (lowercase).
- answer_explanation: a detailed explanation that is at least 5 sentences long, explaining why the correct answer is correct and why all the other answer choices are wrong.
- age: a decimal number representing the patient's age in years (for example, 0.5 for 6 months).
- subject: the number {subject_number} (see subject map below)

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
22 = Pulmonology

Rules:
1. Return a valid JSON object containing exactly these keys, with no extra text.
2. The 'question' must be a detailed, realistic pediatric clinical vignette that is at least 5 sentences long and clearly set in a {setting}.
3. The 'anchor' field must be exactly: {anchor}
4. The 'answer_explanation' must be at least 5 sentences long, explaining why the correct answer is correct and why all the other answer choices are wrong.
5. Do not add any additional keys or text.

Return only the JSON object."""

    
def generate_question(subject_number, anchor, setting):
    prompt = get_question_prompt(subject_number, anchor, setting)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=800,
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
            raise ValueError("Failed to parse JSON from GPT output.")
    return question_json

def send_email(filepath):
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

    msg = EmailMessage()
    msg['Subject'] = f"🩺 Daily USMLE Pediatric Questions - {TODAY}"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_RECIPIENT
    msg.set_content("Attached are today's USMLE-style pediatric questions.")

    with open(filepath, "rb") as f:
        file_data = f.read()
        msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=os.path.basename(filepath))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

def main():
    # If the file exists, load existing questions; otherwise, start fresh.
    if os.path.exists(FILENAME):
        existing_df = pd.read_csv(FILENAME)
        existing_questions = set(existing_df["question"].str.strip().str.lower().tolist())
    else:
        existing_df = None
        existing_questions = set()
    
    new_rows = []
    
    # Predefined lists for anchor types and clinical settings.
    anchor_types = [
        "What is the most likely diagnosis?",
        "What is the next best step in management?",
        "What is the underlying pathophysiology?",
        "What is the appropriate treatment?",
        "What is the expected prognosis?"
    ]
    settings = [
        "pediatrician's office",
        "emergency department",
        "ICU",
        "clinic",
        "inpatient ward"
    ]
    
    # Generate questions for each subject (1 to 22)
    for subject in SUBJECTS:
        # Randomly select anchor and setting
        anchor = random.choice(anchor_types)
        setting = random.choice(settings)
        try:
            question_data = generate_question(subject, anchor, setting)
        except Exception as e:
            print(f"Error generating question for subject {subject}: {e}")
            continue
        # Override record_id with a fresh one
        question_data["record_id"] = generate_record_id()
        question_data["subject"] = subject
        
        # Normalize new question text for duplicate checking
        new_question_text = question_data.get("question", "").strip().lower()
        if new_question_text in existing_questions:
            print(f"Skipping duplicate question for subject {subject}")
            continue
        else:
            existing_questions.add(new_question_text)
        
        ordered_row = [
            question_data.get("record_id", ""),
            question_data.get("question", ""),
            question_data.get("anchor", ""),
            question_data.get("answerchoice_a", ""),
            question_data.get("answerchoice_b", ""),
            question_data.get("answerchoice_c", ""),
            question_data.get("answerchoice_d", ""),
            question_data.get("answerchoice_e", ""),
            question_data.get("correct_answer", ""),
            question_data.get("answer_explanation", ""),
            question_data.get("age", ""),
            question_data.get("subject", "")
        ]
        new_rows.append(ordered_row)
    
    # Convert new questions to DataFrame
    new_df = pd.DataFrame(new_rows, columns=[
        "record_id", "question", "anchor", "answerchoice_a", "answerchoice_b",
        "answerchoice_c", "answerchoice_d", "answerchoice_e", "correct_answer",
        "answer_explanation", "age", "subject"
    ])
    
    # Append new questions to the existing CSV (if any)
    if existing_df is not None:
        updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        updated_df.to_csv(FILENAME, index=False)
    else:
        new_df.to_csv(FILENAME, index=False)
    
    # Send email with the CSV attached
    send_email(FILENAME)

if __name__ == "__main__":
    main()

