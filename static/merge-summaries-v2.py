#!/usr/bin/env python3
import yaml
import re

# Load the main YAML file
with open('david-copperfield-context.yaml', 'r') as f:
    data = yaml.safe_load(f)

# Load summary files
with open('summaries-frontmatter.yaml', 'r') as f:
    frontmatter = yaml.safe_load(f)

with open('summaries-backmatter.yaml', 'r') as f:
    backmatter = yaml.safe_load(f)

# Helper function to normalize summaries (remove embedded newlines)
def normalize_summary(text):
    return ' '.join(text.split())

# Load chapter summaries from text files
def load_chapter_summaries(filename):
    summaries = {}
    with open(filename, 'r') as f:
        content = f.read()

    # Split by CHAPTER header pattern
    chapters = re.split(r'\n(?=CHAPTER \d+:)', content)

    for chapter_text in chapters:
        chapter_text = chapter_text.strip()
        if not chapter_text or not chapter_text.startswith('CHAPTER'):
            continue

        # Extract chapter number
        match = re.match(r'CHAPTER (\d+):', chapter_text)
        if match:
            chapter_num = int(match.group(1))
            # Get text after the title line
            lines = chapter_text.split('\n', 1)
            summary = lines[1].strip() if len(lines) > 1 else ''
            # Remove embedded newlines to create continuous text
            summary = normalize_summary(summary)
            summaries[chapter_num] = summary

    return summaries

ch1_16 = load_chapter_summaries('summaries-chapters-1-16.txt')
ch17_32 = load_chapter_summaries('summaries-chapters-17-32.txt')
ch33_48 = load_chapter_summaries('summaries-chapters-33-48.txt')
ch49_64 = load_chapter_summaries('summaries-chapters-49-64.txt')

# Merge all chapter summaries
all_chapters = {}
all_chapters.update(ch1_16)
all_chapters.update(ch17_32)
all_chapters.update(ch33_48)
all_chapters.update(ch49_64)

print(f"Loaded {len(all_chapters)} chapter summaries")

# Add summaries to the data structure
for item in data:
    href = item['href']

    # Front matter summaries
    if href == 'epub/text/titlepage.xhtml':
        item['summary'] = normalize_summary(frontmatter['titlepage.xhtml'])
    elif href == 'epub/text/imprint.xhtml':
        item['summary'] = normalize_summary(frontmatter['imprint.xhtml'])
    elif href == 'epub/text/preface-1850.xhtml':
        item['summary'] = normalize_summary(frontmatter['preface-1850.xhtml'])
    elif href == 'epub/text/preface.xhtml':
        item['summary'] = normalize_summary(frontmatter['preface.xhtml'])
    elif href == 'epub/text/dedication.xhtml':
        item['summary'] = normalize_summary(frontmatter['dedication.xhtml'])
    elif href == 'epub/text/halftitlepage.xhtml':
        item['summary'] = normalize_summary(frontmatter['halftitlepage.xhtml'])

        # Add chapter summaries
        if 'children' in item:
            for i, chapter in enumerate(item['children'], 1):
                if i in all_chapters:
                    chapter['summary'] = all_chapters[i]
                    print(f"Added summary for Chapter {i}")

    # Back matter summaries
    elif href == 'epub/text/colophon.xhtml':
        item['summary'] = normalize_summary(backmatter['colophon.xhtml'])
    elif href == 'epub/text/uncopyright.xhtml':
        item['summary'] = normalize_summary(backmatter['uncopyright.xhtml'])

# Write the updated YAML file
with open('david-copperfield-context.yaml', 'w') as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, width=100)

print("Summaries merged successfully!")
