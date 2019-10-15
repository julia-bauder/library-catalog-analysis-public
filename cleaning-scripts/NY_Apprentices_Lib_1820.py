#!/usr/bin/env python3

import os
import string
import re
import unicodecsv
import html
from bs4 import BeautifulSoup as bs
from spellchecker import SpellChecker

def main():
    home_directory = os.path.dirname(os.path.dirname(os.path.abspath( __file__ )))
    with open(os.path.join(home_directory, 'extracted_ocr\\NY_Apprentices_Lib_1820.html'), 'r') as f:
        contents = f.read()
        file = html.unescape(bs(contents, 'lxml'))
        catalog = []
        final_catalog = []
        sum_of_heights = 0
        for page in file.find_all('page'):
            #Counting the words that go into the denominator for average word height
            counted_words = 0
            words = page.find_all('word')
            if len(words) == 0:
                continue
            words = sorted(words, key=lambda x: float(x.get('xmin')))
            # First we sorted all of the words on the page from furthest left to furthest right.
            # Now we sort them all again by highest to lowest. Assuming one column of text per page,
            # this does an excellent job of putting all of the words in normal reading order.
            # Will need a different method for catalogs with two columns per page.
            words = sorted(words, key=lambda x: float(x.get('ymin')))
            old_line_y = float(words[0].get('ymin'))
            line = []
            for word in words:
                # Ignoring empty "words." Not sure where they're coming from; this started happening
                # when I switched to ASCII encoding from the problematic-for-other-reasons UTF-8
                if word.text == '':
                    continue
                # Ignoring single lower case letters. These tend to be OCR artifacts that aren't useful
                # if re.match("[a-z]{1}$", word.text):
                #    continue
                # Ignoring et cetera
                if word.text == '&c':
                    continue
                # Ignoring things in all caps because they're typically headers
                # Even the catalogs where they're not necessarily (e.g., Ladies' Lib
                # of Kalamazoo), the OCR usually makes the all caps in running text
                # into normal text.
                # if re.match("[A-Z]{2}", word.text):
                #    continue
                # Needed for Lib Co Boston 1830, where a lot of 1s got turned into Is in
                # the shelf number column
                if word.text == 'I':
                    continue
                # Ignoring random flecks on the page that get turned into punctuation by OCR
                # Combined with number screen below.
                #if re.match("[_ .,*:|'\"\^\-º“{]{1,4}$", word.text):
                #    continue
                # Ignoring common column headings. "Mo." is a common OCR error for an italicized "No."
                if re.match("Vol", word.text) or re.match("No.", word.text) or re.match("Mo.", word.text) or re.match("Shelf", word.text) or re.match("shelf", word.text) or re.match("Size", word.text) or re.match("Title", word.text) or re.match("Donor", word.text):
                    continue
                # Ignoring page numbers -- 1, 2, or 3-digit numbers not followed by "nd", "rd", "th", etc.
                # Can also adjust to ignore shelf numbers when needed (e.g., NY Mechanics 1844)
                # For NY Apprentices' Lib, only ignore words starting w/punctuation if more than two punctuation characters.
                # A lot of flecks in the paper in this catalog wound up being OCRed as stars ahead of words.
                # And a tweak to ignore OCR-eaten numbers:
                # if re.match("[0-9 %_.,*:|'\"\^\-º“]{2,4}$", word.text) or re.search("[0-9]{3,4}", word.text):
                # if re.match("[0-9]{1,4}$", word.text):
                #    continue
                counted_words += 1
                sum_of_heights = sum_of_heights + (float(word.get('ymax')) - float(word.get('ymin')))
                line_y = float(word.get('ymin'))
                # We know we're on a new line of text when the ymin increases more than 7 pixels.
                # 7 pixels was selected empirically based on first several catalogs processed.
                # This may be too large of a number for very small-type catalogs.
                # Changed to 8 because found cases in Milwaukee YMA where 7 was too small.
                if (line_y - 8) > old_line_y:
                    old_line_y = line_y
                    if line:
                        line = sorted(line, key=lambda x: float(x.get('xmin')))
                        catalog.append(line)
                    line = [word]
                else:
                    line.append(word)
            #Append the last one on the page
            if len(line) > 0:
                line = sorted(line, key=lambda x: float(x.get('xmin')))
                catalog.append(line)
            #Process the page
            previous_line_xmin = None
            # Not doing indenting with NY Apprentices'. The shelfmarks are missing from the OCR on some pages
            # (e.g., 10), and without the shelfmarks there's no way to calculate indents with sufficient
            # precision. Since the vast majority of titles are on one line, this shouldn't be a big hit
            # to accuracy.
    average_line_height = sum_of_heights / counted_words
    #average_line_height = sum_of_heights / len(file.find_all('word'))
    with open(os.path.join(home_directory, 'replication\\NY_Apprentices_Lib_1820.csv'), 'wb+') as outfile:
        csvwriter = unicodecsv.writer(outfile, encoding = 'utf-8')
        for item in catalog:
        # Write catalog entries out to a CSV, omitting shelf numbers and sizes
            # Also omit headers, to the extent we can identify them by
            # having a line-height more than 20% larger than average
            # (testing this just on 1st word in line)
            if (float(item[0].get('ymax')) - float(item[0].get('ymin')) < average_line_height * 1.2):
                final_entry = ''
                for vocable in item:
                    # Don't want to include shelf numbers etc. in output.
                    # Do want to include "1st", 12th", etc.
                    # Loosening this for NY Apprentice's Lib, since a lot of shelf numbers wound up
                    # tacked on to first word in title
                    if (sum(c.isalpha() for c in vocable.text) > (len(vocable.text)*.5)) or vocable.text[-1] == 'h' or vocable.text[-1] == 'd' or vocable.text[-1] == 't':
                        # Get rid of punctuation that confuses Solr (including commas and periods, which interact badly with the
                        # fuzzy search ~ when they trail a word). This includes "'s" on the end of words.
                        stripped_vocable = re.sub(r'[\+ - & \| ! , \. ( ) \{ \} \[ \] \^ " ~ \* \? : \\ â€”]', '', vocable.text)
                        stripped_vocable = re.sub(r'[0-9]','',stripped_vocable)
                        stripped_vocable = stripped_vocable.replace("'s", '')
                        # Encoding problem w/Detroit YMA catalog turned 's into this
                        stripped_vocable = stripped_vocable.replace("™s", '')
                        stripped_vocable = stripped_vocable.replace("'", '')
                        stripped_vocable = stripped_vocable.replace("™", '')
                        # For NY Apprentice's Lib, everything after "do" or the volume size is junk, so we're going to stop
                        # adding words to final_entry when we hit one of those.
                        if stripped_vocable == 'do' or stripped_vocable == 'folio' or stripped_vocable == 'quarto' or stripped_vocable == 'octavo' or stripped_vocable == 'oct' or stripped_vocable == 'duodecimo' or stripped_vocable == 'duodec':
                            break
                        final_entry += ' ' + stripped_vocable
                    #else:
                    #    print(vocable.text)
                if final_entry:
                    csvwriter.writerow([final_entry])

if __name__ == '__main__': main()