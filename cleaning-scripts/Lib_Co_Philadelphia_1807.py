#!/usr/bin/env python3

# This tweaked version also works for Lib Co of Philly 1807 and NY Mercantile 1830

import os
import string
import re
import unicodecsv
import html
from bs4 import BeautifulSoup as bs
from spellchecker import SpellChecker

def main():
    home_directory = os.path.dirname(os.path.dirname(os.path.abspath( __file__ )))
    with open(os.path.join(home_directory, 'extracted_ocr\\Lib_Co_Philadelphia_1807.html'), 'r') as f:
        contents = f.read()
        file = html.unescape(bs(contents, 'lxml'))
        catalog = []
        final_catalog = []
        sum_of_heights = 0
        for index, page in enumerate(file.find_all('page')):
            #Counting the words that go into the denominator for average word height
            counted_words = 0
            words = page.find_all('word')
            if len(words) == 0:
                continue
            words.sort(key=lambda x: float(x.get('xmin')))
            # First we sorted all of the words on the page from furthest left to furthest right.
            # Now we sort them all again by highest to lowest. Assuming one column of text per page,
            # this does an excellent job of putting all of the words in normal reading order.
            # Will need a different method for catalogs with two columns per page.
            words.sort(key=lambda x: float(x.get('ymin')))
            old_line_y = float(words[0].get('ymin'))
            line = []
            for word in words:
                # Ignoring empty "words." Not sure where they're coming from; this started happening
                # when I switched to ASCII encoding from the problematic-for-other-reasons UTF-8
                if word.text == '':
                    continue
                # Ignoring single lower case letters. These tend to be OCR artifacts that aren't useful
                if re.match("[a-z]{1}$", word.text):
                    continue
                # Ignoring et cetera
                if word.text == '&c':
                    continue
                # Ignoring things in all caps because they're typically headers
                # Even the catalogs where they're not necessarily (e.g., Ladies' Lib
                # of Kalamazoo), the OCR usually makes the all caps in running text
                # into normal text.
                if re.match("[A-Z]{2}", word.text):
                    continue
                # Needed for Lib Co Boston 1830, where a lot of 1s got turned into Is in
                # the shelf number column
                if word.text == 'I':
                    continue
                if word.text == 'â€':
                    continue
                # Ignoring random flecks on the page that get turned into punctuation by OCR
                # I swear that not all of this punctuation is in the ASCII code space, but I've seen
                # all of it in the OCR extracted by pdftotext with ASCII7 encoding....
                # Have to remove asterisk from this list in cases where it's used to indicate
                # a library-use-only title.
                if re.match("[=%_.,*:;#|'\"\^\-º•§“{}\[\]&→ … — —\-â€■]{1,5}$", word.text):
                    continue
                # if re.match("[_.,*:|'\"\^\-º]$", word.text):
                    #continue
                # Ignoring common column headings. "Mo." is a common OCR error for an italicized "No."
                if re.match("Vol", word.text) or re.match("No.", word.text) or re.match("Mo.", word.text) or re.match("Shelf", word.text) or re.match("Size", word.text):
                    continue
                counted_words += 1
                sum_of_heights = sum_of_heights + (float(word.get('ymax')) - float(word.get('ymin')))
                line_y = float(word.get('ymin'))
                # We know we're on a new line of text when the ymin increases more than 7 pixels.
                # 7 pixels was selected empirically based on first several catalogs processed.
                # This may be too large of a number for very small-type catalogs.
                # Changed to 8 because found cases in Milwaukee YMA where 7 was too small.
                # Changed to 12 because of non-straight lines in Charleston Lib Co.
                if (line_y - 8) > old_line_y:
                    old_line_y = line_y
                    if line:
                        line.sort(key=lambda x: float(x.get('xmin')))
                        catalog.append(line)
                    line = [word]
                else:
                    line.append(word)
            #Append the last one on the page
            if len(line) > 0:
                line.sort(key=lambda x: float(x.get('xmin')))
                catalog.append(line)
            #Process the page, putting together split lines into single entries
            previous_line_xmin = None
            for entry in catalog:
                # Is the new line indented further than the old line? If so,
                # it needs some special handling.
                # If it's the first line on the page, the question is moot.
                if previous_line_xmin == None:
                    indent = 0
                else:
                    this_line_xmin = float(entry[0].get('xmin'))
                    indent = previous_line_xmin - this_line_xmin
                # Allowing 10 pixels of slop to account for skewed scans etc.
                # Most indents are well over 10 pixels; could increase if needed.
                if (indent + 25) < 0 and (re.match("[0-9]{1,5},", entry[0].string)):
                    # If this line is indented and is the start of a new entry (we know
                    # because the first word is a shelf number), then
                    # we want to append to this line everything from
                    # the previous line with an xmin smaller than the xmin of this word.
                    # Since this will carry down all relevant information from the words on the
                    # previous lines, this *should* work even in catalogs with multiple
                    # levels of indents.
                    # 'vocable' because 'word' was already taken in this script
                    # 10 pixels for slop again
                    for vocable in final_catalog[-1]:
                        if (float(vocable.get('xmin')) + 10) < this_line_xmin:
                            entry.append(vocable)
                    # sort it again because we screwed up the sort appending more words to it
                    entry = sorted(entry, key=lambda x: float(x.get('xmin')))
                elif (indent + 25) < 0:
                    # If it's indented but the first word isn't a shelf number,
                    # then it's continuing the previous line.
                    # Try to reassemble hyphenated words. OCR process ate
                    # the hyphens at the end of lines, so we have to guess
                    # if two words go together or not. We'll assume that if the
                    # first word on the second line is not capitalized and is not
                    # recognized by the spellchecker then it should be concatenated
                    # with the last word on the previous line.
                    last_word_of_carryover = final_catalog[-1][-1].string
                    first_word_of_line = entry[0].string
                    if first_word_of_line and (re.match("[A-Z]", first_word_of_line) or re.match("[0-9 \-.,]+", first_word_of_line) or (first_word_of_line.rstrip('.,?!').casefold() in SpellChecker() and last_word_of_carryover.rstrip('.,?!').casefold() in SpellChecker())):
                        final_catalog[-1] += entry
                        final_catalog_sorted = sorted(final_catalog[-1], key=lambda x: float(x.get('xmin')))
                        previous_line_xmin = float(final_catalog_sorted[0].get('xmin'))
                        entry = None
                    else:
                        final_catalog[-1][-1].string = final_catalog[-1][-1].text + entry[0].text
                        del entry[0]
                        final_catalog[-1] += entry
                        final_catalog_sorted = sorted(final_catalog[-1], key=lambda x: float(x.get('xmin')))
                        previous_line_xmin = float(final_catalog_sorted[0].get('xmin'))
                        entry = None
                if entry:
                    entry_sorted = sorted(entry, key=lambda x: float(x.get('xmin')))
                    previous_line_xmin = float(entry_sorted[0].get('xmin'))
                    final_catalog.append(entry)
            catalog = []
    average_line_height = sum_of_heights / counted_words
    #average_line_height = sum_of_heights / len(file.find_all('word'))
    with open(os.path.join(home_directory, 'replication\\Lib_Co_Philadelphia_1807.csv'), 'wb+') as outfile:
        csvwriter = unicodecsv.writer(outfile, encoding = 'utf-8')
        for item in final_catalog:
        # Write catalog entries out to a CSV, omitting shelf numbers and sizes
            # Also omit headers, to the extent we can identify them by
            # having a line-height more than 20% larger than average
            # (testing this just on 1st word in line)
            if (float(item[0].get('ymax')) - float(item[0].get('ymin')) < average_line_height * 1.2):
                final_entry = ''
                for vocable in item:
                    # Don't want to include shelf numbers etc. in output.
                    # Do want to include "1st", 12th", etc.
                    # Also want to get rid of "do"s now that we're done w/them
                    # Get rid of punctuation that confuses Solr (including commas and periods, which interact badly with the
                    # fuzzy search ~ when they trail a word). This includes "'s" on the end of words.
                    stripped_vocable = re.sub(r'[\+ \- & \| ! , \. ( ) \{ \} \[ \] \^ " ~ \* \? : \\ #”`]', ' ', vocable.text)
                    if stripped_vocable == '':
                        continue
                    if stripped_vocable[0].isalpha() or stripped_vocable[-1] == 'h' or stripped_vocable[-1] == 'd' or stripped_vocable[-1] == 't':
                        stripped_vocable = stripped_vocable.replace("'s", '')
                        if stripped_vocable != 'do' and stripped_vocable != 'ditto':
                            final_entry += ' ' + stripped_vocable
                # Remove things that aren't really entries, or that are irrelevant parts of an entry.
                #final_entry = re.sub(r'Presented([ ]{0,2})by(.*)','',final_entry)
                # Changed because sometimes the conversion from OCR mixed up the order
                final_entry = re.sub(r'Presented(.*)by(.*)','',final_entry)
                final_entry = re.sub(r'Gift(.*)of(.*)','',final_entry)
                if re.search(r'(.*) See (.*)', final_entry):
                    continue
                if re.search(r'(.*) The same (.*)', final_entry):
                    continue
                if len(final_entry) < 6:
                    continue
                # Remove mangled headings that were problematic in Lib Co Philly 1807
                if re.match(r'[A-Z]{1}\s{1}[A-Z]{1}\s{1}[A-Z]{1}', final_entry):
                    print(final_entry)
                    continue
                csvwriter.writerow([final_entry])

if __name__ == '__main__': main()