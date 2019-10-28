#!/usr/bin/env python3

import os
import string
import requests
import json
import csv
import unicodecsv

def main():
     # Stopwords longer than 3 characters in Solr stopword list.
     stopwords = ['into','such','that','their','then','there','these','they','this','will','with','miss','mrs','capt','rev','card','copies','copy','volume']
     # Words to ignore entirely
     ignore = ['continue','continued','vol','vols','volume','v','copy','copies','cop','set','sets','folio','fol','4to','8to','8vo','12mo','24mo','do','quarto','octavo','duodecimo','presented','published' 'd', 'o', 'f', 'q', 'from', 'to','by','same','plates','map','maps','engravings','trans','translated','englished','dr','edit','edition','novel']
     # Ignoring places of publication, too, since we want any edition, not a specific one.
     pub_places = ['London','Lond','Philadelphia','Phil','Edinburgh','Edin','Dublin','Dub']
     # Frequently abbreviated names
     expanded_names = {'Nath':'Nathaniel','Wm':'William','Benj':'Benjamin','Edw':'Edward','Chas':'Charles', 'Robt':'Robert', "Rob't":'Robert', 'Thos':'Thomas', 'Geo':'George', 'Alex':'Alexander', 'Edw':'Edward', 'Sam':'Samuel', 'Saml':'Samuel', 'Jas':'James', 'Jos':'Joseph'}
     with open('replication/NY_Apprentices_Lib_1820_with_solr_matches.csv', 'wb+') as outfile:
        with open('replication/NY_Apprentices_Lib_1820.csv', newline='', errors='ignore') as infile:
            parameters = {
                    #'q.op': 'AND',
                    'defType' : 'edismax',
                    #publishDate was set to be one year AFTER the year of publication of the catalog
                    'fq' : 'publishDate:[* TO 1821]',
                    'rows' : '1',
                    'fl' : '*,score',
                    'qf' : 'title_short^750 title_full_unstemmed^600 title_full^400 title^500 title_alt^200 title_new^100 series^50 series2^30 author^500 author_fuller^150 allfields'
                    }
            csvreader = csv.reader(infile)
            csvwriter = unicodecsv.writer(outfile, encoding = 'utf-8')
            for row in csvreader:
              # Filter out the headings in Philly 1807 that got OCRed with spaces between each letter.
              # As well as other OCR junk. No legit title will only have 1 and 2 letter words.
              if row and len(row[0]) > 6:
               sorted_row = sorted(row[0].split(), key=lambda x: len(x))
               longest_word = sorted_row[-1]
               if len(longest_word) > 2:
                query = 'allfields:\''
                words = str.split(row[0])
                # Only searching first 10 words for Philly 1807
                # for word in words[:10]:
                # Dropping the last word in NY Soc 1813 because it's almost always the place of publication
                # use_words = len(row[0]) - 1
                # for word in words[:use_words]:
                for word in words:
                    for abbrev, name in expanded_names.items():
                         if word == abbrev:
                              word = name
                    #If it's not a word that's going to be in the Hathi records, ignore it
                    if word.casefold() in ignore or word.casefold() in stopwords:
                         continue
                    # No slop on words less than 3 letters long. Solr doesn't like that.
                    # Also, slop on stop words ends badly. It causes Solr to look for the
                    # word in the index, but the word isn't in the index because it was
                    # a stopword at index time. So the search fails.
                    elif len(word) > 3:
                         query += ' (' + word + '~ OR ' + word + ')'
                    # Uncomment and use the following lines *only* with heavily-abbreviated catalogs
                    # In final set of pre-1830 catalogs, only used with NY Society Lib
                    # If using these, comment out the two lines immediately above
                    #elif len(word) > 3:
                    #      query += ' +(' + word + '~ OR ' + word + ' OR ' + word + '*)'
                    # elif len(word) > 1: # Not including words of length 1 for Philly 1807, since we need to
                                        # filter out sizes (which are single-capital-letter in Philly 1807)
                    else:
                         query += ' ' + word
                query += '\''
                print(query)
                parameters.update({'q': query})
                r = requests.get('http://solr1.grinnell.edu:8983/solr/biblio/select', params=parameters)
                if r.status_code == 200:
                    root = json.loads(r.text)
                    print(root['response']['numFound'])
                    if root['response']['numFound']:
                         results = root['response']['numFound']
                         if results != 0:
                              doc = root['response']['docs'][0]
                              if 'author' in doc:
                                   author = doc['author'][0]
                              else:
                                   author = ''
                              title = doc['title']
                              solr_id = doc['id']
                              score = doc['score']
                              row.extend([ author, title, score, solr_id ])
                              if 'oclc_num' in doc:
                                   for num in doc['oclc_num']:
                                        row.extend([num])
              csvwriter.writerow(row)
if __name__ == '__main__': main()