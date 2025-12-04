#!/usr/bin/env python3
import yaml

# Load the main YAML file
with open('david-copperfield-context.yaml', 'r') as f:
    data = yaml.safe_load(f)

# Extract summaries organized by section
frontmatter = []
chapters = {i: None for i in range(1, 65)}
backmatter = []

for item in data:
    href = item['href']
    summary = item.get('summary', '')

    # Front matter
    if href == 'epub/text/titlepage.xhtml':
        frontmatter.append(f"TITLEPAGE\n{summary}\n")
    elif href == 'epub/text/imprint.xhtml':
        frontmatter.append(f"IMPRINT\n{summary}\n")
    elif href == 'epub/text/preface-1850.xhtml':
        frontmatter.append(f"PREFACE 1850\n{summary}\n")
    elif href == 'epub/text/preface.xhtml':
        frontmatter.append(f"PREFACE 1869\n{summary}\n")
    elif href == 'epub/text/dedication.xhtml':
        frontmatter.append(f"DEDICATION\n{summary}\n")
    elif href == 'epub/text/halftitlepage.xhtml':
        frontmatter.append(f"HALFTITLEPAGE\n{summary}\n")

        # Extract chapter summaries
        if 'children' in item:
            for i, chapter in enumerate(item['children'], 1):
                title = chapter.get('title', f'Chapter {i}')
                ch_summary = chapter.get('summary', '')
                chapters[i] = f"CHAPTER {i}: {title}\n{ch_summary}"

    # Back matter
    elif href == 'epub/text/colophon.xhtml':
        backmatter.append(f"COLOPHON\n{summary}\n")
    elif href == 'epub/text/uncopyright.xhtml':
        backmatter.append(f"UNCOPYRIGHT\n{summary}\n")

# Write frontmatter
with open('current-summaries-frontmatter.txt', 'w') as f:
    f.write('\n\n'.join(frontmatter))

# Write chapter batches
with open('current-summaries-ch1-16.txt', 'w') as f:
    f.write('\n\n'.join([chapters[i] for i in range(1, 17) if chapters[i]]))

with open('current-summaries-ch17-32.txt', 'w') as f:
    f.write('\n\n'.join([chapters[i] for i in range(17, 33) if chapters[i]]))

with open('current-summaries-ch33-48.txt', 'w') as f:
    f.write('\n\n'.join([chapters[i] for i in range(33, 49) if chapters[i]]))

with open('current-summaries-ch49-64.txt', 'w') as f:
    f.write('\n\n'.join([chapters[i] for i in range(49, 65) if chapters[i]]))

# Write backmatter
with open('current-summaries-backmatter.txt', 'w') as f:
    f.write('\n\n'.join(backmatter))

print("Extracted summaries to 6 text files:")
print("- current-summaries-frontmatter.txt")
print("- current-summaries-ch1-16.txt")
print("- current-summaries-ch17-32.txt")
print("- current-summaries-ch33-48.txt")
print("- current-summaries-ch49-64.txt")
print("- current-summaries-backmatter.txt")
