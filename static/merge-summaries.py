#!/usr/bin/env python3
import yaml
import sys

# Load the main YAML file
with open('david-copperfield-context.yaml', 'r') as f:
    data = yaml.safe_load(f)

# Load summary files
with open('summaries-frontmatter.yaml', 'r') as f:
    frontmatter = yaml.safe_load(f)

with open('summaries-backmatter.yaml', 'r') as f:
    backmatter = yaml.safe_load(f)

# Load chapter summaries from text files
def load_chapter_summaries(filename):
    summaries = {}
    with open(filename, 'r') as f:
        content = f.read()

    # Split by "CHAPTER" to get individual chapters
    chapters = content.split('\nCHAPTER ')[1:]  # Skip first empty split

    for chapter in chapters:
        lines = chapter.split('\n', 1)
        chapter_num_and_title = lines[0].strip()
        chapter_num = int(chapter_num_and_title.split(':')[0])
        summary = lines[1].strip() if len(lines) > 1 else ''
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

# Add summaries to the data structure
for item in data:
    href = item['href']

    # Front matter summaries
    if href == 'epub/text/titlepage.xhtml':
        item['summary'] = frontmatter['titlepage.xhtml']
    elif href == 'epub/text/imprint.xhtml':
        item['summary'] = frontmatter['imprint.xhtml']
    elif href == 'epub/text/preface-1850.xhtml':
        item['summary'] = frontmatter['preface-1850.xhtml']
    elif href == 'epub/text/preface.xhtml':
        item['summary'] = frontmatter['preface.xhtml']
    elif href == 'epub/text/dedication.xhtml':
        item['summary'] = frontmatter['dedication.xhtml']
    elif href == 'epub/text/halftitlepage.xhtml':
        item['summary'] = frontmatter['halftitlepage.xhtml']

        # Add chapter summaries
        if 'children' in item:
            for i, chapter in enumerate(item['children'], 1):
                if i in all_chapters:
                    chapter['summary'] = all_chapters[i]

    # Back matter summaries
    elif href == 'epub/text/colophon.xhtml':
        item['summary'] = backmatter['colophon.xhtml']
    elif href == 'epub/text/uncopyright.xhtml':
        item['summary'] = backmatter['uncopyright.xhtml']

# Write the updated YAML file
with open('david-copperfield-context.yaml', 'w') as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, width=float("inf"))

print("Summaries merged successfully!")
