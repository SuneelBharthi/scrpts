from docx import Document
import json


def is_bold(run):
    return run.bold if run else False


def paragraph_is_bold(paragraph):
    # Check if any run in paragraph is bold
    return any(run.bold for run in paragraph.runs if run.text.strip())


def extract_text(paragraph):
    return paragraph.text.strip()


def parse_docx_to_json(docx_path):
    doc = Document(docx_path)

    data = {"title": None, "description": None, "sections": []}

    paragraphs = [p for p in doc.paragraphs if p.text.strip() != ""]

    # Step 1: Extract main title and description (assume first bold paragraph is title,
    # next paragraph (non-bold) is description)
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        if paragraph_is_bold(p):
            data["title"] = extract_text(p)
            # description expected to be next non-bold paragraph
            j = i + 1
            while j < len(paragraphs) and paragraph_is_bold(paragraphs[j]):
                j += 1
            if j < len(paragraphs):
                data["description"] = extract_text(paragraphs[j])
                i = j + 1
            else:
                i = j
            break
        i += 1

    current_section = None

    # Step 2: Extract sections and banners
    # Heuristic:
    # - Section titles: bold paragraphs NOT immediately followed by description (more than 1 banner under section)
    # - Banner headings: bold paragraphs followed by a non-bold paragraph (banner description)
    # We'll treat any bold paragraph after main section as either section title or banner heading
    while i < len(paragraphs):
        p = paragraphs[i]
        text = extract_text(p)
        if paragraph_is_bold(p):
            # Peek next paragraph (description)
            if i + 1 < len(paragraphs):
                next_p = paragraphs[i + 1]
                if not paragraph_is_bold(next_p):
                    # This is a banner heading + description
                    banner_heading = text
                    banner_description = extract_text(next_p)
                    if current_section is None:
                        # No section yet, create a default unnamed section
                        current_section = {"section_title": None, "banners": []}
                        data["sections"].append(current_section)
                    current_section["banners"].append(
                        {
                            "banner_heading": banner_heading,
                            "banner_description": banner_description,
                        }
                    )
                    i += 2
                    continue
                else:
                    # Next paragraph is bold, so treat this as a section title
                    current_section = {"section_title": text, "banners": []}
                    data["sections"].append(current_section)
                    i += 1
                    continue
            else:
                # Last paragraph and bold, treat as section title
                current_section = {"section_title": text, "banners": []}
                data["sections"].append(current_section)
                i += 1
                continue
        else:
            # Non-bold paragraph alone (no heading before), skip or handle if needed
            i += 1

    return data


def save_json(data, json_path):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    docx_path = "Switches.docx"  # change to your file path
    json_path = "extracted_data.json"

    extracted_data = parse_docx_to_json(docx_path)
    save_json(extracted_data, json_path)
    print(f"Data extracted and saved to {json_path}")
