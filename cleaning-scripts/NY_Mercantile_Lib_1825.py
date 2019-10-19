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
    with open(os.path.join(home_directory, 'extracted_ocr\\NY_Mercantile_Lib_1825.html'), 'r') as f:
        contents = f.read()
        file = html.unescape(bs(contents, 'lxml'))
        catalog = []
        final_catalog = []
        sum_of_heights = 0
        #Counting the words that go into the denominator for average word height
        counted_words = 0
        for index, page in enumerate(file.find_all('page')):
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
                # Encoding error that's pervasive in NY Mercantile 1825
                if word.text == 'ÃƒÂ¢Ã¢â€šÂ¬' or word.text == 'â€':
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
                # if word.text == 'I':
                #    continue
                # Ignoring random flecks on the page that get turned into punctuation by OCR
                # Combined with number screen below.
                # if re.match("[_.,*:|'\"\^\-º]$", word.text):
                    #continue
                # Ignoring common column headings. "Mo." is a common OCR error for an italicized "No."
                # For NY Mercantile 1825 we need "Vol" to identify contents of multi-volume sets.
                # if re.match("Vol", word.text) or
                if re.match("No.", word.text) or re.match("Mo.", word.text) or re.match("Shelf", word.text) or re.match("Size", word.text):
                    continue
                # Ignoring page numbers -- 1, 2, or 3-digit numbers not followed by "nd", "rd", "th", etc.
                # Can also adjust to ignore shelf numbers when needed (e.g., NY Mechanics 1844)
                # And a tweak to ignore OCR-eaten numbers.
                # I swear that not all of this punctuation is in the ASCII code space, but I've seen
                # all of it in the OCR extracted by pdftotext with ASCII7 encoding....
                #if re.match("[0-9 =%_.,*:#|'\"\^\-º•§]{1,4}$", word.text) or re.search("[0-9]{3,4}", word.text):
                if re.match("[ —=%_.,:#|'\"\^\-º•§]{1,4}$", word.text):
                # if re.match("[0-9]{1,4}$", word.text):
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
                # Is it contents for a multi-volume set? We need to flag these for removal, because the TOCs aren't in the HT metadata
                if re.match(r'\s*Vols?\.\s*', entry[0].text) and re.match(r'\s*\d{1,2}(\.|,)\s*', entry[1].text):
                    entry[0].string = 'DELETE_ME'
                # Is the new line indented further than the old line? If so,
                # it needs some special handling.
                # If it's the first line on the page, the question is moot.
                if previous_line_xmin == None:
                    indent = 0
                else:
                    first_real_word = next((y for y in entry if y.text.rstrip('.,?!').casefold() != "do"), None)
                    if first_real_word:
                        this_line_xmin = float(first_real_word.get('xmin'))
                        indent = previous_line_xmin - this_line_xmin
                    else:
                        continue
                # Allowing 10 pixels of slop to account for skewed scans etc.
                # Most indents are well over 10 pixels; could increase if needed.
                if (indent + 10) < 0 and (entry[0].string.rstrip('.,?!') == 'do'):
                    # If this line is indented and not continuing previous line,
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
                elif (indent + 10) < 0 and entry[0].string != "DELETE_ME":
                    # If it's indented but the first word isn't "do", then it's continuing
                    # the previous line.
                    # If it's a TOC, don't append it to the previous line. We want to keep the previous
                    # line if it's the title of the series/set and only remove TOCs
                    # Try to reassemble hyphenated words. OCR process ate
                    # the hyphens at the end of lines, so we have to guess
                    # if two words go together or not. We'll assume that if the
                    # first word on the second line is not capitalized and is not
                    # recognized by the spellchecker then it should be concatenated
                    # with the last word on the previous line.
                    last_word_of_carryover = final_catalog[-1][-1].string
                    first_word_of_line = entry[0].string
                    if first_word_of_line and first_word_of_line != "DELETE_ME" and (re.match("[A-Z]", first_word_of_line) or re.match("[0-9 \-.,]+", first_word_of_line) or (first_word_of_line.rstrip('.,?!').casefold() in SpellChecker() and last_word_of_carryover.rstrip('.,?!').casefold() in SpellChecker())):
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
                if entry and entry[0] != "DELETE_ME":
                    entry_sorted = sorted(entry, key=lambda x: float(x.get('xmin')))
                    previous_line_xmin = float(entry_sorted[0].get('xmin'))
                    final_catalog.append(entry)
            catalog = []
    average_line_height = sum_of_heights / counted_words
    #average_line_height = sum_of_heights / len(file.find_all('word'))
    with open(os.path.join(home_directory, 'replication\\NY_Mercantile_Lib_1825.csv'), 'wb+') as outfile:
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
                    #if we filter out numbers here, then can't use them to identify tables of contents
                    #in the next step
                    #if stripped_vocable[0].isalpha() or stripped_vocable[-1] == 'h' or stripped_vocable[-1] == 'd' or stripped_vocable[-1] == 't':
                    stripped_vocable = stripped_vocable.replace("'s", '')
                    #stripped_vocable = stripped_vocable.replace("'", '')
                    if stripped_vocable.casefold() != 'do' and stripped_vocable.casefold() != 'ditto':
                        final_entry += ' ' + stripped_vocable
                # Catching TOCs that slipped through the first filter for whatever reason (often missing punctuation)
                if re.match(r'\s*Vols?\s*\d{1,2}', final_entry):
                    continue
                for vocable in final_entry.split():
                    if vocable[0].isdigit() and vocable[-1] != 'h' and vocable[-1] != 'd' and stripped_vocable[-1] != 't':
                        final_entry = re.sub(vocable,'',final_entry)
                final_entry = re.sub(r'Presented(.*)by(.*)$','',final_entry)
                final_entry = re.sub(r'Gift(.*)of(.*)$','',final_entry)
                # This is for NY Society 1813 and NY Mercantile 1825. These translation notes break matching every time.
                # final_entry = final_entry.replace("translated from the Latin","")
                final_entry = final_entry.replace("translated from the French","")
                final_entry = final_entry.replace("translated from the German","")
                if final_entry != '':
                    if final_entry.split() and final_entry.split()[0] and final_entry.split()[0] != "DELETE_ME":
                        csvwriter.writerow([final_entry])

if __name__ == '__main__': main()