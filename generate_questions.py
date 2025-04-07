import os
import openai
import pandas as pd
import random
import uuid
import json
from datetime import date

# Set your OpenAI API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# Define the 22 subject numbers
SUBJECTS = list(range(1, 23))  # 1 to 22
TODAY = date.today().isoformat()
FILENAME = f"questions/questions_{TODAY}.csv"

def generate_record_id():
    return uuid.uuid4().hex[:8].upper()

def get_question_prompt(subject_number):
    return f"""Generate a single USMLE-style pediatric question as a JSON object with the following keys:
- record_id: a random string (this value will be overwritten by the script)
- question: a detailed and lengthy clinical vignette describing a realistic pediatric scenario. The vignette should be at least 5 sentences long and mention a clinical setting such as a pediatrician's office, emergency department, ICU, or clinic.
- anchor: a concise clinical question (for example, What is the most likely diagnosis?)
- answerchoice_a: a brief answer option
- answerchoice_b: a brief answer option
- answerchoice_c: a brief answer option
- answerchoice_d: a brief answer option
- answerchoice_e: a brief answer option
- correct_answer: one of "a", "b", "c", "d", or "e" (lowercase)
- answer_explanation: a brief explanation for why the correct answer is correct and why the others are not
- age: a decimal number representing the patient's age in years (e.g., 0.5 for 6 months)
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
2. The 'question' must be a detailed, realistic pediatric clinical vignette that is at least 5 sentences long and mentions the clinical setting.
3. Do not add any additional keys or text.

Return only the JSON object."""


def generate_question(subject_number):
    prompt = get_question_prompt(subject_number)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=6000,
    )
    output = response.choices[0].message['content'].strip()
    try:
        # Try to parse the output as JSON directly.
        question_json = json.loads(output)
    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract JSON from the text.
        first_brace = output.find('{')
        last_brace = output.rfind('}')
        if first_brace != -1 and last_brace != -1:
            output = output[first_brace:last_brace+1]
            question_json = json.loads(output)
        else:
            raise ValueError("Failed to parse JSON from GPT output.")
    return question_json

def main():
    os.makedirs("questions", exist_ok=True)
    rows = []
    generated_questions = set()  # to help avoid duplicates
    attempts = 0

    # Attempt to generate 5 distinct questions (limit attempts to avoid infinite loop)
    while len(rows) < 5 and attempts < 10:
        subject = random.choice(SUBJECTS)
        question_data = generate_question(subject)
        # Check uniqueness using the 'question' text
        question_text = question_data.get("question", "")
        if any(question_text in q for q in generated_questions):
            attempts += 1
            continue
        generated_questions.add(question_text)
        # Override record_id with a new generated one (without quotes issues)
        question_data["record_id"] = generate_record_id()
        # Ensure subject is the correct number (as string or int, but we'll convert to int when writing)
        question_data["subject"] = subject
        # Order the keys as required
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
        rows.append(ordered_row)
        attempts += 1

    df = pd.DataFrame(rows, columns=[
        "record_id", "question", "anchor", "answerchoice_a", "answerchoice_b",
        "answerchoice_c", "answerchoice_d", "answerchoice_e", "correct_answer",
        "answer_explanation", "age", "subject"
    ])
    df.to_csv(FILENAME, index=False)

if __name__ == "__main__":
    main()

